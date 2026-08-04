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
from unihub_insight_api.repositories.postgres_modules import append_reporting_scope
from unihub_insight_api.services import scope_label


TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class ReconciliationResult:
    scope: str
    sales_difference: Decimal
    target_difference: Decimal
    module_difference: Decimal
    cutoff_matches: bool

    @property
    def passed(self) -> bool:
        return (
            abs(self.sales_difference) <= TOLERANCE
            and abs(self.target_difference) <= TOLERANCE
            and abs(self.module_difference) <= TOLERANCE
            and self.cutoff_matches
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
            WHERE {' AND '.join(clauses)}
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
                    WHERE {' AND '.join(clauses)}
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
                    WHERE {' AND '.join(clauses)}
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
    overview, sales, control = await asyncio.gather(
        repository.get_overview(scope),
        repository.get_module(ModuleId.SALES, scope),
        control_totals(pool, scope),
    )
    overview_sales = metric_value(overview.kpis, "sales.total")
    overview_target = metric_value(overview.kpis, "target.progress_pct")
    target_metric = next(item for item in overview.kpis if item.id == "target.progress_pct")
    target_total = decimal(target_metric.supporting_value)
    module_sales = metric_value(sales.kpis, "sales.total")
    del overview_target
    return ReconciliationResult(
        scope=scope_label(scope),
        sales_difference=overview_sales - decimal(control["total_sales"]),
        target_difference=target_total - decimal(control["total_target"]),
        module_difference=module_sales - overview_sales,
        cutoff_matches=overview.meta.as_of == control["last_sale_date"],
    )


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
        results = [
            await reconcile_scope(pool, repository, scope) for scope in scopes
        ]
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
