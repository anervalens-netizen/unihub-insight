from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import asyncpg

from unihub_insight_api.domain import AnalyticsScope, OverviewMeta
from unihub_insight_api.repositories.monthly_review import (
    PostgresMonthlyReviewRepository,
)


MAX_REVIEW_PERIODS = 16
MAX_PRODUCT_CANDIDATES = 500
_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def validate_review_periods(periods: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(periods))
    if not normalized:
        raise ValueError("At least one review period is required")
    if len(normalized) > MAX_REVIEW_PERIODS:
        raise ValueError(
            f"Monthly review is bounded to {MAX_REVIEW_PERIODS} distinct months"
        )
    if any(_PERIOD_PATTERN.fullmatch(period) is None for period in normalized):
        raise ValueError("Monthly review periods must use YYYY-MM")
    return normalized


class ReportingMonthlyReviewRepository(PostgresMonthlyReviewRepository):
    """Production monthly review over canonical monthly reporting models.

    Core sales, quantity, receipt, Focus and working-day values are read only from
    `reporting_agent_month` and `reporting_item_month`. The versioned
    `insight.monthly_review_item_month` view supplements fields absent from those
    models: return value and stable product attributes. The API never queries raw
    `sales_transactions` directly.
    """

    async def _meta_for_review(self, scope: AnalyticsScope) -> OverviewMeta:
        meta = await super()._meta_for_review(scope)
        return meta.model_copy(
            update={
                "source": (
                    "reporting_agent_month/reporting_item_month/"
                    "insight.monthly_review_item_month"
                )
            }
        )

    async def _review_store_rows(
        self,
        scope: AnalyticsScope,
        periods: Sequence[str],
    ) -> Sequence[asyncpg.Record]:
        bounded_periods = validate_review_periods(periods)
        params: list[Any] = [list(bounded_periods)]
        clauses = self._scope_clauses(scope, params)
        agent_filter_core = ""
        agent_filter_supplement = ""
        if scope.agent:
            params.append(scope.agent)
            agent_parameter = len(params)
            agent_filter_core = f"AND fact.agent = ${agent_parameter}"
            agent_filter_supplement = (
                f"AND supplement.agent = ${agent_parameter}"
            )
            target_expression = "agent_target.target_value"
            target_join = f"""
                LEFT JOIN agent_targets agent_target
                  ON agent_target.import_month = requested.import_month
                 AND agent_target.site_code = eligible.site_code
                 AND agent_target.agent = ${agent_parameter}
            """
        else:
            target_expression = "store_target.target_value"
            target_join = """
                LEFT JOIN store_targets store_target
                  ON store_target.import_month = requested.import_month
                 AND store_target.site_code = eligible.site_code
            """
        where_scope = " AND ".join(clauses)

        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH eligible AS MATERIALIZED (
                    SELECT
                        store.site_code,
                        store.locatie,
                        store.firma,
                        store.regional,
                        store.asm
                    FROM stores store
                    WHERE {where_scope}
                ),
                requested AS (
                    SELECT UNNEST($1::text[]) AS import_month
                ),
                core AS (
                    SELECT
                        fact.import_month,
                        fact.site_code,
                        SUM(fact.total_sales) AS sales,
                        SUM(fact.total_quantity) AS units,
                        SUM(fact.focus_quantity) AS focus_units,
                        SUM(fact.receipt_count) AS receipts,
                        SUM(fact.receipt_2plus_count) AS receipt_2plus,
                        MAX(fact.working_days) AS working_days
                    FROM reporting_agent_month fact
                    JOIN eligible USING (site_code)
                    WHERE fact.import_month = ANY($1::text[])
                      {agent_filter_core}
                    GROUP BY fact.import_month, fact.site_code
                ),
                supplement AS (
                    SELECT
                        supplement.import_month,
                        supplement.site_code,
                        SUM(supplement.gross_sales) AS gross_sales,
                        SUM(supplement.return_value) AS return_value
                    FROM insight.monthly_review_item_month supplement
                    JOIN eligible USING (site_code)
                    WHERE supplement.import_month = ANY($1::text[])
                      {agent_filter_supplement}
                    GROUP BY supplement.import_month, supplement.site_code
                )
                SELECT
                    requested.import_month,
                    eligible.site_code,
                    eligible.locatie,
                    eligible.firma,
                    eligible.regional,
                    eligible.asm,
                    COALESCE(core.sales, 0) AS sales,
                    COALESCE(core.units, 0) AS units,
                    COALESCE(core.focus_units, 0) AS focus_units,
                    COALESCE(core.receipts, 0) AS receipts,
                    COALESCE(core.receipt_2plus, 0) AS receipt_2plus,
                    COALESCE(core.working_days, 0) AS working_days,
                    COALESCE(supplement.gross_sales, 0) AS gross_sales,
                    COALESCE(supplement.return_value, 0) AS return_value,
                    COALESCE({target_expression}, 0) AS target
                FROM eligible
                CROSS JOIN requested
                LEFT JOIN core USING (import_month, site_code)
                LEFT JOIN supplement USING (import_month, site_code)
                {target_join}
                ORDER BY requested.import_month, eligible.site_code
                """,
                *params,
            )

    async def _review_agent_rows(
        self,
        scope: AnalyticsScope,
        periods: Sequence[str],
    ) -> Sequence[asyncpg.Record]:
        bounded_periods = validate_review_periods(periods)
        params: list[Any] = [list(bounded_periods)]
        clauses = self._scope_clauses(scope, params)
        agent_filter_core = ""
        agent_filter_supplement = ""
        if scope.agent:
            params.append(scope.agent)
            agent_parameter = len(params)
            agent_filter_core = f"AND fact.agent = ${agent_parameter}"
            agent_filter_supplement = (
                f"AND supplement.agent = ${agent_parameter}"
            )
        where_scope = " AND ".join(clauses)

        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH eligible AS MATERIALIZED (
                    SELECT
                        store.site_code,
                        store.locatie,
                        store.firma,
                        store.regional,
                        store.asm
                    FROM stores store
                    WHERE {where_scope}
                ),
                core AS (
                    SELECT
                        fact.import_month,
                        fact.site_code,
                        fact.agent,
                        SUM(fact.total_sales) AS sales,
                        SUM(fact.total_quantity) AS units,
                        SUM(fact.focus_quantity) AS focus_units,
                        SUM(fact.receipt_count) AS receipts,
                        SUM(fact.receipt_2plus_count) AS receipt_2plus,
                        MAX(fact.working_days) AS working_days
                    FROM reporting_agent_month fact
                    JOIN eligible USING (site_code)
                    WHERE fact.import_month = ANY($1::text[])
                      {agent_filter_core}
                    GROUP BY fact.import_month, fact.site_code, fact.agent
                ),
                supplement AS (
                    SELECT
                        supplement.import_month,
                        supplement.site_code,
                        supplement.agent,
                        SUM(supplement.gross_sales) AS gross_sales,
                        SUM(supplement.return_value) AS return_value
                    FROM insight.monthly_review_item_month supplement
                    JOIN eligible USING (site_code)
                    WHERE supplement.import_month = ANY($1::text[])
                      {agent_filter_supplement}
                    GROUP BY
                        supplement.import_month,
                        supplement.site_code,
                        supplement.agent
                )
                SELECT
                    core.import_month,
                    core.site_code,
                    core.agent,
                    eligible.locatie,
                    eligible.firma,
                    eligible.regional,
                    eligible.asm,
                    core.sales,
                    core.units,
                    core.focus_units,
                    core.receipts,
                    core.receipt_2plus,
                    core.working_days,
                    COALESCE(supplement.gross_sales, 0) AS gross_sales,
                    COALESCE(supplement.return_value, 0) AS return_value,
                    COALESCE(target.target_value, 0) AS target
                FROM core
                JOIN eligible USING (site_code)
                LEFT JOIN supplement USING (import_month, site_code, agent)
                LEFT JOIN agent_targets target USING (import_month, site_code, agent)
                ORDER BY core.import_month, core.site_code, core.agent
                """,
                *params,
            )

    async def _review_product_rows(
        self,
        scope: AnalyticsScope,
        periods: Sequence[str],
    ) -> Sequence[asyncpg.Record]:
        bounded_periods = validate_review_periods(periods)
        params: list[Any] = [list(bounded_periods)]
        clauses = self._scope_clauses(scope, params)
        agent_filter_core = ""
        agent_filter_supplement = ""
        if scope.agent:
            params.append(scope.agent)
            agent_parameter = len(params)
            agent_filter_core = f"AND fact.agent = ${agent_parameter}"
            agent_filter_supplement = (
                f"AND supplement.agent = ${agent_parameter}"
            )
        where_scope = " AND ".join(clauses)

        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH eligible AS MATERIALIZED (
                    SELECT
                        store.site_code,
                        store.locatie,
                        store.firma,
                        store.regional,
                        store.asm
                    FROM stores store
                    WHERE {where_scope}
                ),
                ranked_items AS MATERIALIZED (
                    SELECT fact.item_code
                    FROM reporting_item_month fact
                    JOIN eligible USING (site_code)
                    WHERE fact.import_month = ANY($1::text[])
                      {agent_filter_core}
                    GROUP BY fact.item_code
                    ORDER BY SUM(ABS(fact.total_sales)) DESC
                    LIMIT {MAX_PRODUCT_CANDIDATES}
                ),
                core AS (
                    SELECT
                        fact.import_month,
                        fact.item_code,
                        MAX(fact.item_name) AS item_name,
                        SUM(fact.total_sales) AS sales,
                        SUM(fact.net_quantity) AS units,
                        COUNT(DISTINCT fact.site_code)
                            FILTER (WHERE fact.positive_quantity > 0) AS distribution
                    FROM reporting_item_month fact
                    JOIN eligible USING (site_code)
                    JOIN ranked_items USING (item_code)
                    WHERE fact.import_month = ANY($1::text[])
                      {agent_filter_core}
                    GROUP BY fact.import_month, fact.item_code
                ),
                supplement AS (
                    SELECT
                        supplement.import_month,
                        supplement.item_code,
                        MAX(supplement.item_name) AS item_name,
                        MAX(supplement.brand) AS brand,
                        MAX(supplement.category) AS category,
                        SUM(supplement.gross_sales) AS gross_sales,
                        SUM(supplement.return_value) AS return_value
                    FROM insight.monthly_review_item_month supplement
                    JOIN eligible USING (site_code)
                    JOIN ranked_items USING (item_code)
                    WHERE supplement.import_month = ANY($1::text[])
                      {agent_filter_supplement}
                    GROUP BY supplement.import_month, supplement.item_code
                )
                SELECT
                    core.import_month,
                    core.item_code,
                    COALESCE(supplement.item_name, core.item_name) AS item_name,
                    COALESCE(supplement.brand, 'Necunoscut') AS brand,
                    COALESCE(supplement.category, 'Necategorizat') AS category,
                    core.sales,
                    core.units,
                    COALESCE(supplement.gross_sales, 0) AS gross_sales,
                    COALESCE(supplement.return_value, 0) AS return_value,
                    core.distribution,
                    0 AS receipts,
                    0 AS receipt_2plus,
                    0 AS focus_units,
                    0 AS working_days,
                    0 AS target
                FROM core
                LEFT JOIN supplement USING (import_month, item_code)
                ORDER BY core.import_month, ABS(core.sales) DESC
                """,
                *params,
            )
