#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg

from unihub_insight_api.config import Settings
from unihub_insight_api.db import close_pool, create_pool
from unihub_insight_api.domain import AnalyticsScope, ComparisonMode, ModuleId
from unihub_insight_api.repositories.postgres_hardened import (
    PostgresHardenedInsightRepository,
)
from unihub_insight_api.repositories.postgres_modules import (
    append_reporting_scope,
    finance_metrics,
)
from unihub_insight_api.services import scope_label


TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class ReconciliationResult:
    scope: str
    sales_difference: Decimal
    target_difference: Decimal
    module_difference: Decimal
    cutoff_matches: bool
    domain_differences: dict[str, Decimal]
    unavailable_domains: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return (
            abs(self.sales_difference) <= TOLERANCE
            and abs(self.target_difference) <= TOLERANCE
            and abs(self.module_difference) <= TOLERANCE
            and self.cutoff_matches
            and all(
                abs(value) <= TOLERANCE for value in self.domain_differences.values()
            )
        )


def decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    return value if isinstance(value, Decimal) else Decimal(str(value))


def metric_value(items: list[Any], metric_id: str) -> Decimal:
    for item in items:
        if item.id == metric_id:
            return decimal(item.value)
    raise RuntimeError(f"Missing metric {metric_id}")


async def control_totals(
    pool: asyncpg.Pool,
    scope: AnalyticsScope,
) -> dict[str, Any]:
    params: list[Any] = [scope.period]
    clauses = ["agg.import_month = $1"]
    clauses.extend(
        append_reporting_scope(
            scope,
            alias="agg",
            params=params,
            include_agent=True,
        )
    )
    async with pool.acquire() as connection:
        row = await connection.fetchrow(
            f"""
            SELECT
                COALESCE(SUM(agg.total_sales), 0) AS total_sales,
                COALESCE(SUM(agg.total_quantity), 0) AS total_quantity,
                COALESCE(SUM(agg.receipt_count), 0) AS total_receipts,
                COALESCE(SUM(agg.receipt_2plus_count), 0) AS receipt_2plus_count,
                MAX(agg.sale_date) AS last_sale_date,
                COUNT(DISTINCT agg.site_code) AS stores
            FROM reporting_agent_day agg
            WHERE {" AND ".join(clauses)}
            """,
            *params,
        )
        if row is None:
            raise RuntimeError("Control-total query returned no aggregate row")

        target_params = list(params)
        if scope.agent:
            target_params.append(scope.agent)
            agent_placeholder = f"${len(target_params)}"
            target = await connection.fetchval(
                f"""
                WITH filtered_sites AS MATERIALIZED (
                    SELECT DISTINCT agg.site_code
                    FROM reporting_agent_day agg
                    WHERE {" AND ".join(clauses)}
                )
                SELECT COALESCE(SUM(COALESCE(
                    NULLIF(to_jsonb(target)->>'target_value', '')::NUMERIC,
                    NULLIF(to_jsonb(target)->>'target', '')::NUMERIC,
                    0
                )), 0)
                FROM agent_targets target
                JOIN filtered_sites sites
                  ON sites.site_code = COALESCE(
                      to_jsonb(target)->>'site_code',
                      to_jsonb(target)->>'store_code'
                  )
                WHERE target.import_month = $1
                  AND LOWER(BTRIM(COALESCE(
                      to_jsonb(target)->>'agent',
                      to_jsonb(target)->>'agent_code',
                      to_jsonb(target)->>'agent_name',
                      ''
                  ))) = LOWER(BTRIM({agent_placeholder}))
                """,
                *target_params,
            )
        else:
            target = await connection.fetchval(
                f"""
                WITH filtered_sites AS MATERIALIZED (
                    SELECT DISTINCT agg.site_code
                    FROM reporting_agent_day agg
                    WHERE {" AND ".join(clauses)}
                )
                SELECT COALESCE(SUM(target.target_value), 0)
                FROM store_targets target
                JOIN filtered_sites sites USING (site_code)
                WHERE target.import_month = $1
                """,
                *params,
            )
    return {**dict(row), "total_target": decimal(target)}


async def reconcile_scope(
    pool: asyncpg.Pool,
    repository: PostgresHardenedInsightRepository,
    scope: AnalyticsScope,
) -> ReconciliationResult:
    overview, sales, control, specialized = await asyncio.gather(
        repository.get_overview(scope),
        repository.get_module(ModuleId.SALES, scope),
        control_totals(pool, scope),
        specialized_differences(pool, repository, scope),
    )
    domain_differences, unavailable_domains = specialized
    overview_sales = metric_value(overview.kpis, "sales.total")
    overview_target = metric_value(overview.kpis, "target.progress_pct")
    target_metric = next(
        item for item in overview.kpis if item.id == "target.progress_pct"
    )
    target_total = decimal(target_metric.supporting_value)
    module_sales = metric_value(sales.kpis, "sales.total")
    del overview_target
    return ReconciliationResult(
        scope=scope_label(scope),
        sales_difference=overview_sales - decimal(control["total_sales"]),
        target_difference=target_total - decimal(control["total_target"]),
        module_difference=module_sales - overview_sales,
        cutoff_matches=overview.meta.as_of == control["last_sale_date"],
        domain_differences=domain_differences,
        unavailable_domains=unavailable_domains,
    )


async def specialized_differences(
    pool: asyncpg.Pool,
    repository: PostgresHardenedInsightRepository,
    scope: AnalyticsScope,
) -> tuple[dict[str, Decimal], tuple[str, ...]]:
    if scope.agent:
        return {}, ()
    snapshot = await repository.resolve_snapshot(scope)
    eligible_domains = {
        domain
        for domain, source in snapshot.sources.items()
        if source.status.value != "unavailable"
    }
    required_domains = {"campaigns", "workforce", "finance", "planning"}
    if not (scope.regional or scope.asm or scope.stores):
        required_domains.add("compensation")
    unavailable_domains = tuple(sorted(required_domains - eligible_domains))
    params: list[Any] = [scope.period]
    scope_clauses = append_reporting_scope(
        scope, alias="row", params=params, include_agent=False
    )
    scope_sql = " AND ".join(scope_clauses) if scope_clauses else "TRUE"
    finance_params: list[Any] = [scope.period]
    finance_clauses: list[str] = []
    if scope.stores:
        finance_params.append(list(scope.stores))
        finance_clauses.append(f"row.site_code = ANY(${len(finance_params)}::text[])")
    else:
        if scope.firm:
            finance_params.append(scope.firm)
            finance_clauses.append(
                f"(LOWER(row.firma) = LOWER(${len(finance_params)}) "
                f"OR (row.is_unallocated AND LOWER(row.company_name) = LOWER(${len(finance_params)})))"
            )
        if scope.regional:
            finance_params.append(scope.regional)
            finance_clauses.append(f"row.regional = ${len(finance_params)}")
        if scope.asm:
            finance_params.append(scope.asm)
            finance_clauses.append(f"row.asm = ${len(finance_params)}")
    finance_scope_sql = " AND ".join(finance_clauses) if finance_clauses else "TRUE"
    async with pool.acquire() as connection:
        campaign = await connection.fetchrow(
            f"""
            SELECT COALESCE(SUM(row.actual_sales), 0) AS sales,
                   COUNT(DISTINCT row.site_code)
                       FILTER (WHERE row.actual_sales > 0)::numeric AS stores,
                   COALESCE(MAX(row.active_product_count), 0)::numeric AS products
            FROM reporting_campaign_month_v1 row
            WHERE row.period = $1 AND {scope_sql}
            """,
            *params,
        )
        workforce = await connection.fetchrow(
            f"""
            SELECT COUNT(DISTINCT row.agent)::numeric AS headcount
            FROM reporting_agent_month row
            WHERE row.import_month = $1 AND {scope_sql}
            """,
            *params,
        )
        finance_rows = await connection.fetch(
            f"""
            SELECT row.category_code, COALESCE(SUM(row.amount), 0) AS amount
            FROM reporting_finance_month_v1 row
            WHERE row.period = $1 AND {finance_scope_sql}
            GROUP BY row.category_code
            """,
            *finance_params,
        )
        planning = await connection.fetchrow(
            f"""
            SELECT COALESCE(SUM(row.forecast_value), 0) AS forecast,
                   COALESCE(SUM(row.target_value), 0) AS target
            FROM reporting_planning_scenario_v1 row
            WHERE row.period = $1 AND {scope_sql}
            """,
            *params,
        )
        compensation = None
        if "compensation" in eligible_domains and not (
            scope.regional or scope.asm or scope.stores
        ):
            compensation_params: list[Any] = [scope.period, scope.firm or "__ALL__"]
            compensation = await connection.fetchrow(
                """
                SELECT payroll_total, average_salary_eligible, median_salary
                FROM reporting_compensation_month_v1
                WHERE period = $1 AND LOWER(company_name) = LOWER($2)
                """,
                *compensation_params,
            )

    requested_modules = [
        (domain, module)
        for domain, module in (
            ("campaigns", ModuleId.CAMPAIGNS),
            ("workforce", ModuleId.WORKFORCE),
            ("finance", ModuleId.FINANCE),
            ("planning", ModuleId.PLANNING),
            ("compensation", ModuleId.COMPENSATION),
        )
        if domain in eligible_domains and (domain != "compensation" or compensation is not None)
    ]
    responses = await asyncio.gather(
        *(repository.get_module(module, scope) for _, module in requested_modules)
    )
    modules = {domain: response for (domain, _), response in zip(requested_modules, responses)}
    differences: dict[str, Decimal] = {}
    campaigns = modules.get("campaigns")
    if campaigns is not None:
        differences.update(
            {
                "campaigns.focus_sales": metric_value(
                    campaigns.kpis, "campaigns.focus_sales"
                )
                - decimal(campaign["sales"] if campaign else None),
                "campaigns.active_stores": metric_value(
                    campaigns.kpis, "campaigns.active_stores"
                )
                - decimal(campaign["stores"] if campaign else None),
                "campaigns.active_products": metric_value(
                    campaigns.kpis, "campaigns.active_products"
                )
                - decimal(campaign["products"] if campaign else None),
            }
        )
    workforce_module = modules.get("workforce")
    if workforce_module is not None:
        differences["workforce.headcount"] = metric_value(
            workforce_module.kpis, "workforce.headcount"
        ) - decimal(workforce["headcount"] if workforce else None)
    finance_module = modules.get("finance")
    if finance_module is not None:
        finance_control = finance_metrics(
            {str(row["category_code"]): decimal(row["amount"]) for row in finance_rows}
        )
        differences.update(
            {
                "finance.revenue": metric_value(finance_module.kpis, "finance.revenue")
                - finance_control["revenue"],
                "finance.ebit": metric_value(finance_module.kpis, "finance.ebit")
                - finance_control["ebit"],
            }
        )
    planning_module = modules.get("planning")
    if planning_module is not None:
        differences["planning.forecast"] = metric_value(
            planning_module.kpis, "planning.forecast"
        ) - decimal(planning["forecast"] if planning else None)
    if planning_module is not None and planning and any(
        item.id == "planning.target_gap" for item in planning_module.kpis
    ):
        expected_gap = decimal(planning["forecast"]) - decimal(planning["target"])
        differences["planning.target_gap"] = (
            metric_value(planning_module.kpis, "planning.target_gap") - expected_gap
        )
    compensation_module = modules.get("compensation")
    if compensation is not None and compensation_module is not None:
        differences.update(
            {
                "compensation.payroll": metric_value(
                    compensation_module.kpis, "compensation.payroll"
                )
                - decimal(compensation["payroll_total"]),
                "compensation.average": metric_value(
                    compensation_module.kpis, "compensation.average"
                )
                - decimal(compensation["average_salary_eligible"]),
                "compensation.median": metric_value(
                    compensation_module.kpis, "compensation.median"
                )
                - decimal(compensation["median_salary"]),
            }
        )
    return differences, unavailable_domains


def explicit_scope(arguments: argparse.Namespace) -> AnalyticsScope:
    stores = tuple(
        item.strip() for item in (arguments.stores or "").split(",") if item.strip()
    )
    return AnalyticsScope(
        period=arguments.period,
        comparison=ComparisonMode.NONE,
        firm=arguments.firm,
        regional=arguments.regional,
        asm=arguments.asm,
        stores=stores,
        agent=arguments.agent,
    )


async def sample_scopes(
    repository: PostgresHardenedInsightRepository,
    period: str,
) -> list[AnalyticsScope]:
    options = await repository.get_filter_options(period)
    scopes = [AnalyticsScope(period=period, comparison=ComparisonMode.NONE)]
    scopes.extend(
        AnalyticsScope(period=period, comparison=ComparisonMode.NONE, firm=value)
        for value in options.firms[:2]
    )
    scopes.extend(
        AnalyticsScope(period=period, comparison=ComparisonMode.NONE, regional=value)
        for value in options.regionals[:2]
    )
    scopes.extend(
        AnalyticsScope(
            period=period,
            comparison=ComparisonMode.NONE,
            stores=(store.site_code,),
        )
        for store in options.stores[:5]
    )
    scopes.extend(
        AnalyticsScope(
            period=period,
            comparison=ComparisonMode.NONE,
            stores=(agent.site_code,),
            agent=agent.name,
        )
        for agent in options.agents[:5]
    )
    return scopes


async def run(arguments: argparse.Namespace) -> int:
    dsn = os.environ.get("UNIHUB_INSIGHT_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("UNIHUB_INSIGHT_DATABASE_URL is required")
    settings = Settings(
        environment="test",
        data_mode="postgres",
        auth_mode="demo",
        database_url=dsn,
    )
    pool = await create_pool(settings)
    try:
        repository = PostgresHardenedInsightRepository(pool)
        scopes = (
            await sample_scopes(repository, arguments.period)
            if arguments.matrix
            else [explicit_scope(arguments)]
        )
        results = [await reconcile_scope(pool, repository, scope) for scope in scopes]
    finally:
        await close_pool(pool)

    payload = [
        {
            "scope": result.scope,
            "passed": result.passed,
            "sales_difference": str(result.sales_difference),
            "target_difference": str(result.target_difference),
            "module_difference": str(result.module_difference),
            "cutoff_matches": result.cutoff_matches,
            "domain_differences": {
                key: str(value) for key, value in result.domain_differences.items()
            },
            "unavailable_domains": list(result.unavailable_domains),
        }
        for result in results
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all(result.passed for result in results) else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile Insight contracts against canonical Retail read models"
    )
    parser.add_argument("--period", required=True)
    parser.add_argument("--firm")
    parser.add_argument("--regional")
    parser.add_argument("--asm")
    parser.add_argument("--stores")
    parser.add_argument("--agent")
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="test a bounded representative network/firm/RM/store/agent matrix",
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(run(arguments)))


if __name__ == "__main__":
    main()
