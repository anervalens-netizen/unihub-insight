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
PORTFOLIO_DIMENSIONS = ("category", "subcategory", "brand", "product")


@dataclass(frozen=True)
class ReconciliationResult:
    sample_case: str
    scope: str
    sales_difference: Decimal
    target_difference: Decimal
    module_difference: Decimal
    cutoff_matches: bool
    domain_differences: dict[str, Decimal]
    unavailable_domains: tuple[str, ...]
    incomplete_domains: dict[str, str]
    matrix_missing_cases: tuple[str, ...] = ()

    @property
    def numeric_passed(self) -> bool:
        return (
            abs(self.sales_difference) <= TOLERANCE
            and abs(self.target_difference) <= TOLERANCE
            and abs(self.module_difference) <= TOLERANCE
            and self.cutoff_matches
            and all(
                abs(value) <= TOLERANCE for value in self.domain_differences.values()
            )
        )

    @property
    def authoritative_passed(self) -> bool:
        return (
            self.numeric_passed
            and not self.incomplete_domains
            and not self.matrix_missing_cases
        )

    @property
    def passed(self) -> bool:
        return self.authoritative_passed


def decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    return value if isinstance(value, Decimal) else Decimal(str(value))


def metric_value(items: list[Any], metric_id: str) -> Decimal:
    value = optional_metric_value(items, metric_id)
    if value is not None:
        return value
    raise RuntimeError(f"Missing metric {metric_id}")


def optional_metric_value(items: list[Any], metric_id: str) -> Decimal | None:
    for item in items:
        if item.id == metric_id:
            return decimal(item.value)
    return None


def visit_metric_differences(
    control: dict[str, Any],
    performance: Any,
) -> dict[str, Decimal]:
    visits = performance.visits
    kpis = visits.kpis if visits is not None else []
    expected_present = decimal(control["total_visits"]) > 0
    actual_present = bool(kpis)
    differences = {
        "visits.presence": Decimal(int(actual_present)) - Decimal(int(expected_present))
    }
    if not actual_present:
        return differences
    differences.update(
        {
            "visits.total": metric_value(kpis, "visits.total")
            - decimal(control["total_visits"]),
            "visits.distinct_stores": metric_value(kpis, "visits.distinct_stores")
            - decimal(control["distinct_stores"]),
            "visits.avg_completion": metric_value(kpis, "visits.avg_completion")
            - decimal(control["avg_completion"]),
            "visits.checklist_score": metric_value(kpis, "visits.checklist_score")
            - decimal(control["checklist_score"]),
        }
    )
    return differences


def portfolio_metric_differences(
    control: dict[str, dict[str, Decimal]],
    sales: Any,
) -> dict[str, Decimal]:
    """Compare each Sales Portfolio roll-up with its authoritative control total."""
    differences: dict[str, Decimal] = {}
    for dimension in PORTFOLIO_DIMENSIONS:
        prefix = f"sales.portfolio.{dimension}"
        portfolio = sales.portfolio.get(dimension)
        if portfolio is None:
            differences[f"{prefix}.presence"] = Decimal(-1)
            continue
        metrics = portfolio.kpis
        expected = control[dimension]
        differences.update(
            {
                f"{prefix}.sales": metric_value(metrics, "sales.portfolio_sales")
                - expected["sales"],
                f"{prefix}.net_quantity": metric_value(
                    metrics, "sales.portfolio_net_quantity"
                )
                - expected["net_quantity"],
                f"{prefix}.entities": Decimal(len(portfolio.breakdown))
                - expected["entities"],
            }
        )
        if dimension in {"brand", "product"}:
            differences[f"{prefix}.return_quantity"] = (
                metric_value(metrics, "sales.portfolio_return_quantity")
                - expected["return_quantity"]
            )
        if dimension == "product":
            differences[f"{prefix}.receipt_incidence"] = (
                metric_value(metrics, "sales.portfolio_receipt_incidence")
                - expected["receipt_incidence"]
            )
    return differences


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
            target_params.append(list(scope.agent))
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
                  ))) IN (
                      SELECT LOWER(BTRIM(selected.value))
                      FROM UNNEST({agent_placeholder}::text[]) AS selected(value)
                  )
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


async def portfolio_control_totals(
    pool: asyncpg.Pool,
    scope: AnalyticsScope,
) -> dict[str, dict[str, Decimal]]:
    """Read Sales Portfolio controls independently of the API aggregation slices."""
    category_params: list[Any] = [scope.period]
    category_clauses = ["category.import_month = $1"]
    category_clauses.extend(
        append_reporting_scope(scope, alias="category", params=category_params)
    )
    item_params: list[Any] = [scope.period]
    item_clauses = ["item.import_month = $1"]
    item_clauses.extend(append_reporting_scope(scope, alias="item", params=item_params))
    async with pool.acquire() as connection:
        category = await connection.fetchrow(
            f"""
            SELECT
                COALESCE(SUM(category.total_sales), 0) AS total_sales,
                COALESCE(SUM(category.total_quantity), 0)::numeric AS net_quantity,
                COUNT(DISTINCT category.category)::numeric AS category_entities,
                COUNT(DISTINCT ROW(category.category, category.subcategory))::numeric
                    AS subcategory_entities
            FROM reporting_category_month category
            WHERE {" AND ".join(category_clauses)}
            """,
            *category_params,
        )
        items = await connection.fetchrow(
            f"""
            WITH attributes AS (
                SELECT
                    supplement.import_month,
                    supplement.site_code,
                    supplement.agent,
                    supplement.item_code,
                    MAX(NULLIF(BTRIM(supplement.brand), '')) AS brand
                FROM insight.monthly_review_item_month supplement
                WHERE supplement.import_month = $1
                GROUP BY
                    supplement.import_month,
                    supplement.site_code,
                    supplement.agent,
                    supplement.item_code
            ), scoped AS (
                SELECT
                    item.item_code,
                    item.total_sales,
                    item.net_quantity,
                    item.return_quantity,
                    item.receipt_count,
                    attributes.brand
                FROM reporting_item_month item
                LEFT JOIN attributes
                  ON attributes.import_month = item.import_month
                 AND attributes.site_code IS NOT DISTINCT FROM item.site_code
                 AND attributes.agent IS NOT DISTINCT FROM item.agent
                 AND attributes.item_code = item.item_code
                WHERE {" AND ".join(item_clauses)}
            )
            SELECT
                COALESCE(SUM(scoped.total_sales), 0) AS total_sales,
                COALESCE(SUM(scoped.net_quantity), 0)::numeric AS net_quantity,
                COALESCE(SUM(scoped.return_quantity), 0)::numeric AS return_quantity,
                COALESCE(SUM(scoped.receipt_count), 0)::numeric AS receipt_incidence,
                COUNT(DISTINCT COALESCE(scoped.brand, 'Necunoscut'))::numeric
                    AS brand_entities,
                COUNT(DISTINCT scoped.item_code)::numeric AS product_entities
            FROM scoped
            """,
            *item_params,
        )
    if category is None or items is None:
        raise RuntimeError("Sales Portfolio control query returned no aggregate row")
    category_sales = decimal(category["total_sales"])
    category_quantity = decimal(category["net_quantity"])
    item_sales = decimal(items["total_sales"])
    item_quantity = decimal(items["net_quantity"])
    return {
        "category": {
            "sales": category_sales,
            "net_quantity": category_quantity,
            "entities": decimal(category["category_entities"]),
        },
        "subcategory": {
            "sales": category_sales,
            "net_quantity": category_quantity,
            "entities": decimal(category["subcategory_entities"]),
        },
        "brand": {
            "sales": item_sales,
            "net_quantity": item_quantity,
            "return_quantity": decimal(items["return_quantity"]),
            "entities": decimal(items["brand_entities"]),
        },
        "product": {
            "sales": item_sales,
            "net_quantity": item_quantity,
            "return_quantity": decimal(items["return_quantity"]),
            "receipt_incidence": decimal(items["receipt_incidence"]),
            "entities": decimal(items["product_entities"]),
        },
    }


async def reconcile_scope(
    pool: asyncpg.Pool,
    repository: PostgresHardenedInsightRepository,
    scope: AnalyticsScope,
    *,
    sample_case: str = "explicit",
    matrix_missing_cases: tuple[str, ...] = (),
) -> ReconciliationResult:
    overview, sales, control, portfolio_control, specialized = await asyncio.gather(
        repository.get_overview(scope),
        repository.get_module(ModuleId.SALES, scope),
        control_totals(pool, scope),
        portfolio_control_totals(pool, scope),
        specialized_differences(pool, repository, scope),
    )
    domain_differences, unavailable_domains, source_statuses = specialized
    domain_differences.update(portfolio_metric_differences(portfolio_control, sales))
    overview_sales = metric_value(overview.kpis, "sales.total")
    overview_target = metric_value(overview.kpis, "target.progress_pct")
    target_metric = next(
        item for item in overview.kpis if item.id == "target.progress_pct"
    )
    target_total = decimal(target_metric.supporting_value)
    module_sales = metric_value(sales.kpis, "sales.total")
    del overview_target
    return ReconciliationResult(
        sample_case=sample_case,
        scope=scope_label(scope),
        sales_difference=overview_sales - decimal(control["total_sales"]),
        target_difference=target_total - decimal(control["total_target"]),
        module_difference=module_sales - overview_sales,
        cutoff_matches=overview.meta.as_of == control["last_sale_date"],
        domain_differences=domain_differences,
        unavailable_domains=unavailable_domains,
        incomplete_domains={
            domain: status
            for domain, status in sorted(source_statuses.items())
            if status != "official"
        },
        matrix_missing_cases=matrix_missing_cases,
    )


async def specialized_differences(
    pool: asyncpg.Pool,
    repository: PostgresHardenedInsightRepository,
    scope: AnalyticsScope,
) -> tuple[dict[str, Decimal], tuple[str, ...], dict[str, str]]:
    snapshot = await repository.resolve_snapshot(scope)
    eligible_domains = {
        domain
        for domain, source in snapshot.sources.items()
        if source.status.value != "unavailable"
    }
    required_domains = {"sales", "planning", "contest", "grile"}
    if not scope.agent:
        required_domains.update({"campaigns", "workforce", "finance", "visits"})
        if not (scope.regional or scope.asm or scope.stores):
            required_domains.add("compensation")
    source_statuses = {
        domain: (
            snapshot.sources[domain].status.value
            if domain in snapshot.sources
            else "unavailable"
        )
        for domain in required_domains
    }
    unavailable_domains = set(required_domains - eligible_domains)
    if scope.agent:
        return {}, tuple(sorted(unavailable_domains)), source_statuses
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
            finance_params.append(list(scope.regional))
            finance_clauses.append(
                f"row.regional = ANY(${len(finance_params)}::text[])"
            )
        if scope.asm:
            finance_params.append(scope.asm)
            finance_clauses.append(f"row.asm = ${len(finance_params)}")
    finance_scope_sql = " AND ".join(finance_clauses) if finance_clauses else "TRUE"
    async with pool.acquire() as connection:
        campaign_rows = await connection.fetch(
            f"""
            WITH campaign_base AS MATERIALIZED (
                SELECT row.*
                FROM reporting_campaign_month_v3 row
                WHERE row.period = $1
                  AND row.status <> 'unavailable'
                  AND NOT (
                      row.mechanism = 'promo'
                      AND row.mechanism_variant = 'same_model_screen_camera'
                  )
                  AND {scope_sql}
            )
            SELECT row.mechanism,
                   COALESCE(SUM(row.actual_sales), 0) AS sales,
                   COALESCE(SUM(row.actual_quantity), 0)::numeric AS quantity,
                   COUNT(DISTINCT row.site_code) FILTER (
                       WHERE (row.mechanism = 'promo' AND (
                                  COALESCE(row.promo_qualifying_bons, 0) > 0
                               OR COALESCE(row.promo_discounted_units, 0) > 0
                               OR COALESCE(row.promo_discount_value, 0) > 0
                           ))
                          OR (row.mechanism = 'incentive' AND (
                                  row.incentive_store_qualified
                               OR COALESCE(row.incentive_qualified_quantity, 0) > 0
                               OR COALESCE(row.incentive_value, 0) > 0
                           ))
                          OR (row.mechanism = 'focus' AND (
                                  COALESCE(row.actual_sales, 0) <> 0
                               OR COALESCE(row.actual_quantity, 0) <> 0
                           ))
                   )::numeric AS stores,
                   COALESCE((
                       SELECT COUNT(DISTINCT product_code)
                       FROM campaign_base product_row
                       CROSS JOIN LATERAL UNNEST(product_row.active_product_codes)
                           AS product(product_code)
                       WHERE product_row.mechanism = row.mechanism
                   ), 0)::numeric AS products,
                   COALESCE(SUM(row.promo_qualifying_bons), 0)::numeric
                       AS promo_qualifying_bons,
                   COUNT(row.promo_qualifying_bons)::numeric
                       AS promo_qualifying_bons_published,
                   COALESCE(SUM(row.promo_discounted_units), 0)::numeric
                       AS promo_discounted_units,
                   COALESCE(SUM(row.promo_discount_value), 0)
                       AS promo_discount_value,
                   COALESCE(SUM(row.incentive_eligible_quantity), 0)::numeric
                       AS incentive_eligible_quantity,
                   COALESCE(SUM(row.incentive_qualified_quantity), 0)::numeric
                       AS incentive_qualified_quantity,
                   COALESCE(SUM(row.incentive_value), 0) AS incentive_value
            FROM campaign_base row
            GROUP BY row.mechanism
            """,
            *params,
        )
        folii_control = await connection.fetchrow(
            f"""
            SELECT
                COUNT(*)::numeric AS rows,
                COALESCE(SUM(row.actual_sales), 0) AS sales,
                COALESCE(SUM(row.actual_quantity), 0)::numeric AS quantity,
                COALESCE(SUM(row.promo_discount_value), 0) AS discount,
                COUNT(DISTINCT row.site_code) FILTER (
                    WHERE COALESCE(row.promo_qualifying_bons, 0) > 0
                       OR COALESCE(row.promo_discounted_units, 0) > 0
                       OR COALESCE(row.promo_discount_value, 0) > 0
                )::numeric AS stores,
                COALESCE(SUM(row.promo_discounted_units), 0)::numeric AS discounted_units,
                COALESCE(SUM(row.promo_qualifying_bons), 0)::numeric AS qualifying_receipts,
                COUNT(row.promo_qualifying_bons)::numeric AS qualifying_receipts_published
            FROM reporting_campaign_month_v3 AS row
            WHERE row.period = $1
              AND row.mechanism = 'promo'
              AND row.mechanism_variant = 'same_model_screen_camera'
              AND row.status <> 'unavailable'
              AND {scope_sql}
            """,
            *params,
        )
        contest_control = None
        if "contest" in eligible_domains:
            contest_control = await connection.fetchrow(
                f"""
                SELECT
                    COUNT(*)::numeric AS rows,
                    COALESCE(SUM(row.focus_units), 0)::numeric AS focus_units,
                    COALESCE(SUM(row.promo_units), 0)::numeric AS promo_units,
                    COALESCE(SUM(row.price_units), 0)::numeric AS price_units,
                    COALESCE(SUM(row.focus_points), 0)::numeric AS focus_points,
                    COALESCE(SUM(row.promo_points), 0)::numeric AS promo_points,
                    COALESCE(SUM(row.price_points), 0)::numeric AS price_points,
                    COALESCE(SUM(row.total_points), 0)::numeric AS points_total
                FROM reporting_contest_month_v1 AS row
                WHERE row.period = $1
                  AND row.status <> 'unavailable'
                  AND {scope_sql}
                """,
                *params,
            )
        focus_active_products = await connection.fetchval(
            f"""
            SELECT COUNT(DISTINCT row.item_code)::numeric
            FROM reporting_focus_item_month row
            WHERE row.import_month = $1 AND {scope_sql}
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
        grile_control = None
        if "grile" in eligible_domains:
            grile_control = await connection.fetchrow(
                f"""
                SELECT
                    COUNT(*)::numeric AS observed_stores,
                    COUNT(*) FILTER (
                        WHERE lower(COALESCE(row.fill_status, '')) <> 'completat'
                           OR lower(COALESCE(row.target_status, '')) <> 'ok'
                           OR lower(COALESCE(row.sales_status, '')) <> 'ok'
                    )::numeric AS problem_stores
                FROM reporting_grile_month_v2 AS row
                WHERE row.run_month = $1
                  AND row.status <> 'unavailable'
                  AND {scope_sql}
                """,
                *params,
            )
        visits = await connection.fetchrow(
            f"""
            SELECT COALESCE(SUM(row.total_visits), 0)::numeric AS total_visits,
                   COUNT(DISTINCT row.site_code)::numeric AS distinct_stores,
                   COALESCE(ROUND(
                       SUM(row.avg_completion * row.total_visits)
                           FILTER (WHERE row.avg_completion IS NOT NULL)
                       / NULLIF(SUM(row.total_visits)
                           FILTER (WHERE row.avg_completion IS NOT NULL), 0),
                       2
                   ), 0) AS avg_completion,
                   COALESCE(ROUND(
                       SUM(row.checklist_score * row.total_visits)
                           FILTER (WHERE row.checklist_score IS NOT NULL)
                       / NULLIF(SUM(row.total_visits)
                           FILTER (WHERE row.checklist_score IS NOT NULL), 0),
                       2
                   ), 0) AS checklist_score
            FROM reporting_visit_month_v2 row
            WHERE row.period = $1 AND {scope_sql}
            """,
            *params,
        )
        finance_rows: list[asyncpg.Record] = []
        if "finance" in eligible_domains:
            finance_rows = await connection.fetch(
                f"""
                SELECT row.category_code, COALESCE(SUM(row.amount), 0) AS amount
                FROM reporting_finance_month_v1 row
                WHERE row.period = $1 AND {finance_scope_sql}
                GROUP BY row.category_code
                """,
                *finance_params,
            )
        planning = None
        if "planning" in eligible_domains:
            planning = await connection.fetchrow(
                f"""
                SELECT
                    COALESCE(SUM(row.forecast_value) FILTER (
                        WHERE row.authority_kind = 'forecast'
                          AND row.metric = 'sales_value'
                          AND row.status <> 'unavailable'
                    ), 0) AS forecast,
                    COALESCE(SUM(row.target_value) FILTER (
                        WHERE row.authority_kind = 'target'
                          AND row.status <> 'unavailable'
                    ), 0) AS target
                FROM reporting_planning_scenario_v2 row
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
            ("contest", ModuleId.CAMPAIGNS),
            ("workforce", ModuleId.WORKFORCE),
            ("grile", ModuleId.WORKFORCE),
            ("finance", ModuleId.FINANCE),
            ("planning", ModuleId.PLANNING),
            ("visits", ModuleId.PERFORMANCE),
            ("compensation", ModuleId.COMPENSATION),
        )
        if domain in eligible_domains
        and (domain != "compensation" or compensation is not None)
    ]
    responses = await asyncio.gather(
        *(repository.get_module(module, scope) for _, module in requested_modules)
    )
    modules = {
        domain: response for (domain, _), response in zip(requested_modules, responses)
    }
    differences: dict[str, Decimal] = {}
    campaigns = modules.get("campaigns")
    if campaigns is not None:
        campaign_controls = {str(row["mechanism"]): row for row in campaign_rows}
        focus_control = campaign_controls.get("focus")
        differences.update(
            {
                "campaigns.focus_sales": metric_value(
                    campaigns.kpis, "campaigns.focus_sales"
                )
                - decimal(focus_control["sales"] if focus_control else None),
                "campaigns.active_stores": metric_value(
                    campaigns.kpis, "campaigns.active_stores"
                )
                - decimal(focus_control["stores"] if focus_control else None),
                "campaigns.active_products": metric_value(
                    campaigns.kpis, "campaigns.active_products"
                )
                - decimal(focus_active_products),
            }
        )
        for mechanism, reward_field, qualifying_field, eligible_field in (
            (
                "promo",
                "promo_discount_value",
                "promo_qualifying_bons",
                "promo_discounted_units",
            ),
            (
                "incentive",
                "incentive_value",
                "incentive_qualified_quantity",
                "incentive_eligible_quantity",
            ),
        ):
            control = campaign_controls.get(mechanism)
            campaign_slice = campaigns.campaigns.get(mechanism)
            if control is None or campaign_slice is None:
                differences[f"campaigns.{mechanism}.presence"] = Decimal(-1)
                continue
            prefix = f"campaigns.{mechanism}"
            differences.update(
                {
                    f"{prefix}_sales": metric_value(
                        campaign_slice.kpis, f"{prefix}_sales"
                    )
                    - decimal(control["sales"]),
                    f"{prefix}_quantity": metric_value(
                        campaign_slice.kpis, f"{prefix}_quantity"
                    )
                    - decimal(control["quantity"]),
                    f"{prefix}_{'discount' if mechanism == 'promo' else 'reward'}": metric_value(
                        campaign_slice.kpis,
                        f"{prefix}_{'discount' if mechanism == 'promo' else 'reward'}",
                    )
                    - decimal(control[reward_field]),
                    f"{prefix}_active_stores": metric_value(
                        campaign_slice.kpis, f"{prefix}_active_stores"
                    )
                    - decimal(control["stores"]),
                    f"{prefix}_active_products": metric_value(
                        campaign_slice.kpis, f"{prefix}_active_products"
                    )
                    - decimal(control["products"]),
                    f"{prefix}_{'discounted_units' if mechanism == 'promo' else 'eligible_quantity'}": metric_value(
                        campaign_slice.kpis,
                        f"{prefix}_{'discounted_units' if mechanism == 'promo' else 'eligible_quantity'}",
                    )
                    - decimal(control[eligible_field]),
                }
            )
            qualifying_metric = f"{prefix}_{'qualifying_receipts' if mechanism == 'promo' else 'qualified_quantity'}"
            qualifying_value = optional_metric_value(
                campaign_slice.kpis, qualifying_metric
            )
            if (
                mechanism == "promo"
                and decimal(control["promo_qualifying_bons_published"]) == 0
            ):
                differences[f"{qualifying_metric}.presence"] = Decimal(
                    int(qualifying_value is not None)
                )
            else:
                differences[qualifying_metric] = decimal(qualifying_value) - decimal(
                    control[qualifying_field]
                )
        folii_slice = campaigns.campaigns.get("folii")
        if folii_slice is None:
            differences["campaigns.folii.presence"] = Decimal(-1)
        elif decimal(folii_control["rows"] if folii_control else None) == 0:
            differences["campaigns.folii.presence"] = Decimal(
                int(bool(folii_slice.kpis))
            )
        else:
            folii_metrics = folii_slice.kpis
            differences.update(
                {
                    "campaigns.folii_sales": metric_value(
                        folii_metrics, "campaigns.folii_sales"
                    )
                    - decimal(folii_control["sales"]),
                    "campaigns.folii_quantity": metric_value(
                        folii_metrics, "campaigns.folii_quantity"
                    )
                    - decimal(folii_control["quantity"]),
                    "campaigns.folii_discount": metric_value(
                        folii_metrics, "campaigns.folii_discount"
                    )
                    - decimal(folii_control["discount"]),
                    "campaigns.folii_active_stores": metric_value(
                        folii_metrics, "campaigns.folii_active_stores"
                    )
                    - decimal(folii_control["stores"]),
                    "campaigns.folii_discounted_units": metric_value(
                        folii_metrics, "campaigns.folii_discounted_units"
                    )
                    - decimal(folii_control["discounted_units"]),
                }
            )
            receipt = optional_metric_value(
                folii_metrics, "campaigns.folii_qualifying_receipts"
            )
            if decimal(folii_control["qualifying_receipts_published"]) == 0:
                differences["campaigns.folii_qualifying_receipts.presence"] = Decimal(
                    int(receipt is not None)
                )
            else:
                differences["campaigns.folii_qualifying_receipts"] = decimal(
                    receipt
                ) - decimal(folii_control["qualifying_receipts"])
    contest_module = modules.get("contest")
    if contest_module is not None and contest_control is not None:
        contest_slice = contest_module.campaigns.get("contest")
        if contest_slice is None:
            differences["campaigns.contest.presence"] = Decimal(-1)
        elif decimal(contest_control["rows"]) == 0:
            differences["campaigns.contest.presence"] = Decimal(
                int(bool(contest_slice.kpis))
            )
        else:
            differences.update(
                {
                    "campaigns.contest_points_total": metric_value(
                        contest_slice.kpis, "campaigns.contest_points_total"
                    )
                    - decimal(contest_control["points_total"]),
                    "campaigns.contest_focus_units": metric_value(
                        contest_slice.kpis, "campaigns.contest_focus_units"
                    )
                    - decimal(contest_control["focus_units"]),
                    "campaigns.contest_promo_units": metric_value(
                        contest_slice.kpis, "campaigns.contest_promo_units"
                    )
                    - decimal(contest_control["promo_units"]),
                    "campaigns.contest_price_units": metric_value(
                        contest_slice.kpis, "campaigns.contest_price_units"
                    )
                    - decimal(contest_control["price_units"]),
                    "campaigns.contest_focus_points": metric_value(
                        contest_slice.kpis, "campaigns.contest_focus_points"
                    )
                    - decimal(contest_control["focus_points"]),
                    "campaigns.contest_promo_points": metric_value(
                        contest_slice.kpis, "campaigns.contest_promo_points"
                    )
                    - decimal(contest_control["promo_points"]),
                    "campaigns.contest_price_points": metric_value(
                        contest_slice.kpis, "campaigns.contest_price_points"
                    )
                    - decimal(contest_control["price_points"]),
                }
            )
    workforce_module = modules.get("workforce")
    if workforce_module is not None:
        differences["workforce.headcount"] = metric_value(
            workforce_module.kpis, "workforce.headcount"
        ) - decimal(workforce["headcount"] if workforce else None)
    grile_module = modules.get("grile")
    if grile_module is not None and grile_control is not None:
        grile_slice = grile_module.subviews.get("grile")
        if grile_slice is None:
            differences["grile.presence"] = Decimal(-1)
        elif decimal(grile_control["observed_stores"]) == 0:
            differences["grile.presence"] = Decimal(int(bool(grile_slice.kpis)))
        else:
            differences.update(
                {
                    "grile.observed_stores": metric_value(
                        grile_slice.kpis, "grile.observed_stores"
                    )
                    - decimal(grile_control["observed_stores"]),
                    "grile.problem_stores": metric_value(
                        grile_slice.kpis, "grile.problem_stores"
                    )
                    - decimal(grile_control["problem_stores"]),
                }
            )
    performance_module = modules.get("visits")
    if performance_module is not None and visits is not None:
        differences.update(visit_metric_differences(dict(visits), performance_module))
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
        planning_forecast = optional_metric_value(
            planning_module.kpis, "planning.forecast"
        )
        if planning_forecast is None:
            unavailable_domains.add("planning")
        else:
            differences["planning.forecast"] = planning_forecast - decimal(
                planning["forecast"] if planning else None
            )
    if (
        planning_module is not None
        and "planning" not in unavailable_domains
        and planning
        and any(item.id == "planning.target_gap" for item in planning_module.kpis)
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
    return differences, tuple(sorted(unavailable_domains)), source_statuses


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
    pool: asyncpg.Pool,
    repository: PostgresHardenedInsightRepository,
    period: str,
) -> tuple[list[tuple[str, AnalyticsScope]], tuple[str, ...]]:
    options = await repository.get_filter_options(period)
    scopes = [
        ("network", AnalyticsScope(period=period, comparison=ComparisonMode.NONE))
    ]
    scopes.extend(
        (
            f"firm:{index}",
            AnalyticsScope(period=period, comparison=ComparisonMode.NONE, firm=value),
        )
        for index, value in enumerate(options.firms[:2], start=1)
    )
    scopes.extend(
        (
            f"regional:{index}",
            AnalyticsScope(
                period=period, comparison=ComparisonMode.NONE, regional=value
            ),
        )
        for index, value in enumerate(options.regionals[:2], start=1)
    )
    scopes.extend(
        (
            f"asm:{index}",
            AnalyticsScope(period=period, comparison=ComparisonMode.NONE, asm=value),
        )
        for index, value in enumerate(options.asms[:2], start=1)
    )
    scopes.extend(
        (
            f"store:{index}",
            AnalyticsScope(
                period=period,
                comparison=ComparisonMode.NONE,
                stores=(store.site_code,),
            ),
        )
        for index, store in enumerate(options.stores[:5], start=1)
    )
    scopes.extend(
        (
            f"agent:{index}",
            AnalyticsScope(
                period=period,
                comparison=ComparisonMode.NONE,
                stores=(agent.site_code,),
                agent=agent.name,
            ),
        )
        for index, agent in enumerate(options.agents[:5], start=1)
    )
    async with pool.acquire() as connection:
        return_store = await connection.fetchval(
            """
            SELECT sales.site_code
            FROM reporting_sales_day_v1 sales
            WHERE sales.period = $1
            GROUP BY sales.site_code
            HAVING SUM(sales.return_quantity) < 0
            ORDER BY SUM(sales.return_quantity), sales.site_code
            LIMIT 1
            """,
            period,
        )
        transferred_store = await connection.fetchval(
            """
            WITH transferred AS (
                SELECT daily.site_code
                FROM reporting_agent_day daily
                GROUP BY daily.site_code
                HAVING COUNT(DISTINCT daily.firma) > 1
            )
            SELECT daily.site_code
            FROM reporting_agent_day daily
            JOIN transferred USING (site_code)
            WHERE daily.import_month = $1
            GROUP BY daily.site_code
            ORDER BY daily.site_code
            LIMIT 1
            """,
            period,
        )
        partial_target = await connection.fetchrow(
            """
            WITH period_days AS (
                SELECT COUNT(DISTINCT daily.sale_date)::int AS active_days
                FROM reporting_agent_day daily
                WHERE daily.import_month = $1
            )
            SELECT monthly.site_code, monthly.agent
            FROM reporting_agent_month monthly
            JOIN agent_targets target USING (import_month, site_code, agent)
            CROSS JOIN period_days
            WHERE monthly.import_month = $1
              AND target.target_value > 0
              AND monthly.working_days BETWEEN 1 AND period_days.active_days - 1
            ORDER BY monthly.working_days, monthly.site_code, monthly.agent
            LIMIT 1
            """,
            period,
        )
    missing_cases = [
        label
        for label, value in (
            ("store-with-returns", return_store),
            ("historically-transferred-store", transferred_store),
            ("partial-month-target-agent", partial_target),
        )
        if value is None
    ]
    edge_scopes: list[tuple[str, AnalyticsScope]] = []
    if return_store is not None:
        edge_scopes.append(
            (
                "store-with-returns",
                AnalyticsScope(
                    period=period,
                    comparison=ComparisonMode.NONE,
                    stores=(str(return_store),),
                ),
            ),
        )
    if transferred_store is not None:
        edge_scopes.append(
            (
                "historically-transferred-store",
                AnalyticsScope(
                    period=period,
                    comparison=ComparisonMode.NONE,
                    stores=(str(transferred_store),),
                ),
            ),
        )
    if partial_target is not None:
        edge_scopes.append(
            (
                "partial-month-target-agent",
                AnalyticsScope(
                    period=period,
                    comparison=ComparisonMode.NONE,
                    stores=(str(partial_target["site_code"]),),
                    agent=str(partial_target["agent"]),
                ),
            ),
        )
    scopes.extend(edge_scopes)
    return scopes, tuple(missing_cases)


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
        if arguments.matrix:
            cases, matrix_missing_cases = await sample_scopes(
                pool, repository, arguments.period
            )
        else:
            cases = [("explicit", explicit_scope(arguments))]
            matrix_missing_cases = ()
        results = [
            await reconcile_scope(
                pool,
                repository,
                scope,
                sample_case=sample_case,
                matrix_missing_cases=matrix_missing_cases,
            )
            for sample_case, scope in cases
        ]
    finally:
        await close_pool(pool)

    payload = [
        {
            "sample_case": result.sample_case,
            "scope": result.scope,
            "passed": result.passed,
            "numeric_passed": result.numeric_passed,
            "authoritative_passed": result.authoritative_passed,
            "sales_difference": str(result.sales_difference),
            "target_difference": str(result.target_difference),
            "module_difference": str(result.module_difference),
            "cutoff_matches": result.cutoff_matches,
            "domain_differences": {
                key: str(value) for key, value in result.domain_differences.items()
            },
            "unavailable_domains": list(result.unavailable_domains),
            "incomplete_domains": result.incomplete_domains,
            "matrix_missing_cases": list(result.matrix_missing_cases),
        }
        for result in results
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    reconciled = all(
        result.numeric_passed if arguments.numeric_only else result.authoritative_passed
        for result in results
    )
    accepted = reconciled and (
        arguments.allow_missing_cases or not matrix_missing_cases
    )
    return 0 if accepted else 1


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
        help="test a bounded representative network/firm/RM/ASM/store/agent matrix",
    )
    parser.add_argument(
        "--numeric-only",
        action="store_true",
        help="exit successfully on zero differences even when a required source is not official",
    )
    parser.add_argument(
        "--allow-missing-cases",
        action="store_true",
        help="diagnostic only: do not fail when a required matrix sample is absent",
    )
    arguments = parser.parse_args()
    raise SystemExit(asyncio.run(run(arguments)))


if __name__ == "__main__":
    main()
