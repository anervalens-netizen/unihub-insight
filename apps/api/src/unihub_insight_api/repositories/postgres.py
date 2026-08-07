from __future__ import annotations

import asyncio
import calendar
import hashlib
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import asyncpg

from unihub_insight_api.domain import (
    AlertSeverity,
    AnalyticalSnapshot,
    AnalyticsScope,
    DailyPoint,
    DataMode,
    DimensionShare,
    FilterAgent,
    FilterOptionsResponse,
    FilterStore,
    InsightAlert,
    KpiMetric,
    MetricUnit,
    OverviewMeta,
    OverviewResponse,
    PerformanceRow,
    RiskLevel,
    SourceDomain,
    SourceMetadata,
    SourceStatus,
)
from unihub_insight_api.services import previous_period, scope_label

MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value: Any) -> Decimal:
    return _decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _percent(value: Any) -> Decimal:
    return _decimal(value).quantize(PERCENT, rounding=ROUND_HALF_UP)


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator <= 0:
        return None
    return _percent(numerator * Decimal("100") / denominator)


def _delta(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return _percent((current - previous) * Decimal("100") / previous)


def _risk(progress: Decimal | None) -> RiskLevel:
    if progress is None or progress < Decimal("80"):
        return RiskLevel.RISK
    if progress < Decimal("95"):
        return RiskLevel.WATCH
    return RiskLevel.HEALTHY


class PostgresAnalyticsRepository:
    """Read-only adapter over UniHub Retail canonical reporting models."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def resolve_snapshot(self, scope: AnalyticsScope) -> AnalyticalSnapshot:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT domain, period, source, source_generation, authority,
                       authority_head, contract_version, rule_version, status,
                       as_of, cutoff, is_final, coverage_numerator,
                       coverage_denominator, produced_at, warnings
                FROM reporting_source_snapshot_v6
                WHERE period = $1
                ORDER BY domain
                """,
                scope.period,
            )
        sources: dict[str, SourceMetadata] = {}
        for row in rows:
            domain = SourceDomain(str(row["domain"]))
            status_value = str(row["status"])
            sources[domain.value] = SourceMetadata(
                domain=domain,
                source=str(row["source"]),
                period=str(row["period"]),
                cutoff=row["cutoff"] if isinstance(row["cutoff"], date) else None,
                as_of=row["as_of"] if isinstance(row["as_of"], date) else None,
                is_final=bool(row["is_final"]),
                coverage_numerator=(int(row["coverage_numerator"]) if row["coverage_numerator"] is not None else None),
                coverage_denominator=(
                    int(row["coverage_denominator"]) if row["coverage_denominator"] is not None else None
                ),
                source_generation=str(row["source_generation"]) if row["source_generation"] else None,
                authority=str(row["authority"]),
                authority_head=str(row["authority_head"]) if row["authority_head"] else None,
                contract_version=int(row["contract_version"]),
                rule_version=str(row["rule_version"]) if row["rule_version"] else None,
                status=SourceStatus(status_value),
                produced_at=row["produced_at"],
                warnings=tuple(str(item) for item in (row["warnings"] or ())),
            )
        generation_material = "|".join(
            f"{key}:{value.source_generation}:{value.authority_head}:{value.status.value}"
            for key, value in sorted(sources.items())
        )
        digest = hashlib.sha256(f"{scope.period}|{generation_material}".encode()).hexdigest()
        return AnalyticalSnapshot(
            id=f"retail-v6-{scope.period}-{digest[:32]}",
            period=scope.period,
            sources=sources,
        )

    async def get_filter_options(self, period: str) -> FilterOptionsResponse:
        option_rows, period_rows = await asyncio.gather(
            self._fetch_options(period),
            self._fetch_periods(),
        )
        stores_by_code: dict[str, FilterStore] = {}
        agents_by_key: dict[tuple[str, str], FilterAgent] = {}
        for row in option_rows:
            site_code = str(row["site_code"])
            store = FilterStore(
                site_code=site_code,
                label=str(row["locatie"]),
                firm=str(row["firma"]),
                regional=str(row["regional"]),
                asm=str(row["asm"]) if row["asm"] else None,
            )
            stores_by_code.setdefault(site_code, store)
            agent_name = str(row["agent"] or "").strip()
            if agent_name:
                agents_by_key.setdefault(
                    (agent_name, site_code),
                    FilterAgent(
                        name=agent_name,
                        site_code=site_code,
                        firm=store.firm,
                        regional=store.regional,
                        asm=store.asm,
                    ),
                )

        stores = sorted(stores_by_code.values(), key=lambda item: (item.label, item.site_code))
        agents = sorted(agents_by_key.values(), key=lambda item: (item.name, item.site_code))
        return FilterOptionsResponse(
            periods=[str(row["import_month"]) for row in period_rows],
            firms=sorted({item.firm for item in stores}),
            regionals=sorted({item.regional for item in stores}),
            asms=sorted({item.asm for item in stores if item.asm}),
            stores=stores,
            agents=agents,
            data_mode=DataMode.POSTGRES,
        )

    async def get_overview(self, scope: AnalyticsScope) -> OverviewResponse:
        snapshot = await self.resolve_snapshot(scope)
        sales_source = snapshot.sources.get(SourceDomain.SALES.value)
        comparison_period = previous_period(scope.period, scope.comparison)
        current_tasks = (
            self._fetch_summary(scope, scope.period),
            self._fetch_daily(scope, scope.period),
            self._fetch_contribution(scope, scope.period),
            self._fetch_performance(scope, scope.period),
        )
        if comparison_period:
            (
                summary,
                daily_rows,
                contribution_rows,
                performance_rows,
                comparison_summary,
                comparison_daily,
                comparison_performance,
            ) = await asyncio.gather(
                *current_tasks,
                self._fetch_summary(scope, comparison_period),
                self._fetch_daily(scope, comparison_period),
                self._fetch_performance(scope, comparison_period),
            )
        else:
            summary, daily_rows, contribution_rows, performance_rows = await asyncio.gather(*current_tasks)
            comparison_summary = None
            comparison_daily = []
            comparison_performance = []

        total_sales = _money(summary["total_sales"])
        total_target = _money(summary["total_target"])
        total_receipts = int(summary["total_receipts"] or 0)
        receipt_2plus = int(summary["receipt_2plus_count"] or 0)
        as_of = summary["last_sale_date"]
        is_final = bool(summary["is_month_final"])
        year, month = (int(part) for part in scope.period.split("-"))
        days_in_month = calendar.monthrange(year, month)[1]
        cutoff_day = as_of.day if isinstance(as_of, date) else 0
        forecast = (
            _money(total_sales / Decimal(cutoff_day) * Decimal(days_in_month))
            if cutoff_day > 0 and not is_final
            else total_sales
        )
        target_progress = _ratio(total_sales, total_target)
        forecast_progress = _ratio(forecast, total_target)
        receipt_2plus_pct = (
            _percent(Decimal(receipt_2plus) * Decimal("100") / Decimal(total_receipts))
            if total_receipts > 0
            else Decimal(0)
        )

        previous_sales = _money(comparison_summary["total_sales"]) if comparison_summary is not None else Decimal(0)
        sales_delta = _delta(total_sales, previous_sales) if comparison_period else None
        comparison_by_day = self._cumulative_by_day(comparison_daily)
        current_by_day = self._cumulative_by_day(daily_rows)
        daily_points: list[DailyPoint] = []
        last_comparison: Decimal | None = None
        for day in range(1, days_in_month + 1):
            if day in comparison_by_day:
                last_comparison = comparison_by_day[day]
            actual = current_by_day.get(day) if day <= cutoff_day else None
            projected = None
            if cutoff_day > 0 and not is_final and day >= cutoff_day:
                projected = _money(total_sales / Decimal(cutoff_day) * Decimal(day))
            daily_points.append(
                DailyPoint(
                    day=day,
                    sales=actual,
                    target_pace=(
                        _money(total_target * Decimal(day) / Decimal(days_in_month)) if total_target > 0 else Decimal(0)
                    ),
                    forecast=projected,
                    comparison=last_comparison,
                )
            )

        comparison_sales_by_store = {
            str(row["site_code"]): _money(row["total_sales"]) for row in comparison_performance
        }
        performance = self._performance_view(performance_rows, comparison_sales_by_store)
        contribution = self._contribution_view(contribution_rows, total_sales)
        alerts = self._alerts(forecast_progress, performance, cutoff_day)

        average_daily = _money(total_sales / Decimal(max(cutoff_day, 1)))
        return OverviewResponse(
            meta=OverviewMeta(
                period=scope.period,
                comparison=scope.comparison,
                as_of=as_of if isinstance(as_of, date) else None,
                is_final=is_final,
                data_mode=DataMode.POSTGRES,
                scope_label=scope_label(scope),
                generated_at=datetime.now(UTC),
                source=sales_source.source if sales_source else "unihub-reporting",
                analytical_snapshot_id=snapshot.id,
                snapshot_contract_version=snapshot.contract_version,
                sources={SourceDomain.SALES: sales_source} if sales_source else {},
            ),
            kpis=[
                KpiMetric(
                    id="sales.total",
                    label="Vânzări",
                    value=total_sales,
                    unit=MetricUnit.CURRENCY,
                    delta_pct=sales_delta,
                    delta_label="față de reper" if comparison_period else None,
                    risk=(RiskLevel.HEALTHY if sales_delta is not None and sales_delta >= 0 else RiskLevel.WATCH),
                    supporting_value=average_daily,
                    supporting_label="Medie / zi acoperită",
                ),
                KpiMetric(
                    id="target.progress_pct",
                    label="Realizare target",
                    value=target_progress or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=_risk(forecast_progress),
                    supporting_value=total_target,
                    supporting_label="Target",
                ),
                KpiMetric(
                    id="forecast.linear",
                    label="Forecast run-rate",
                    value=forecast,
                    unit=MetricUnit.CURRENCY,
                    risk=_risk(forecast_progress),
                    supporting_value=forecast_progress,
                    supporting_label="Forecast % target",
                ),
                KpiMetric(
                    id="receipt_2plus_pct",
                    label="Bonuri 2+",
                    value=receipt_2plus_pct,
                    unit=MetricUnit.PERCENT,
                    risk=(RiskLevel.HEALTHY if receipt_2plus_pct >= Decimal("32") else RiskLevel.WATCH),
                    supporting_value=Decimal(total_receipts),
                    supporting_label="Bonuri totale",
                ),
            ],
            daily=daily_points,
            contribution=contribution,
            performance=performance,
            alerts=alerts,
        )

    async def _fetch_options(self, period: str) -> Sequence[asyncpg.Record]:
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                """
                SELECT DISTINCT
                    agg.firma,
                    agg.regional,
                    agg.asm,
                    agg.site_code,
                    agg.locatie,
                    agg.agent
                FROM reporting_agent_month agg
                WHERE agg.import_month = $1
                  AND agg.locatie NOT ILIKE 'TR %'
                ORDER BY agg.firma, agg.regional, agg.asm, agg.locatie, agg.agent
                """,
                period,
            )

    async def _fetch_periods(self) -> Sequence[asyncpg.Record]:
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                """
                SELECT DISTINCT import_month
                FROM reporting_agent_month
                ORDER BY import_month DESC
                """
            )

    async def _fetch_summary(self, scope: AnalyticsScope, period: str) -> asyncpg.Record:
        clauses, params = self._scope_sql(scope, period)
        target_source = self._target_source_sql(scope, params)
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                WITH filtered AS MATERIALIZED (
                    SELECT
                        agg.site_code,
                        agg.sale_date,
                        agg.total_sales,
                        agg.total_quantity,
                        agg.receipt_count,
                        agg.receipt_2plus_count,
                        agg.focus_quantity
                    FROM reporting_agent_day agg
                    WHERE {" AND ".join(clauses)}
                ),
                target_summary AS (
                    SELECT COALESCE(SUM(target.target_value), 0) AS total_target
                    FROM (
                        {target_source}
                    ) target
                    WHERE EXISTS (
                          SELECT 1 FROM filtered item WHERE item.site_code = target.site_code
                      )
                ),
                snapshot AS (
                    SELECT is_final AS is_month_final
                    FROM reporting_source_snapshot_v6
                    WHERE domain = 'sales' AND period = $1
                    ORDER BY produced_at DESC
                    LIMIT 1
                )
                SELECT
                    COALESCE(SUM(filtered.total_sales), 0) AS total_sales,
                    COALESCE(SUM(filtered.total_quantity), 0)::INT AS total_quantity,
                    COALESCE(SUM(filtered.receipt_count), 0)::INT AS total_receipts,
                    COALESCE(SUM(filtered.receipt_2plus_count), 0)::INT AS receipt_2plus_count,
                    COALESCE(SUM(filtered.focus_quantity), 0)::INT AS focus_quantity,
                    COUNT(DISTINCT filtered.site_code)::INT AS total_stores,
                    MAX(filtered.sale_date) AS last_sale_date,
                    COALESCE((SELECT total_target FROM target_summary), 0) AS total_target,
                    COALESCE((SELECT is_month_final FROM snapshot), true) AS is_month_final
                FROM filtered
                """,
                *params,
            )
        if row is None:
            raise RuntimeError("Overview summary query returned no aggregate row.")
        return row

    async def _fetch_daily(self, scope: AnalyticsScope, period: str) -> Sequence[asyncpg.Record]:
        clauses, params = self._scope_sql(scope, period)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH daily AS (
                    SELECT
                        agg.sale_date,
                        COALESCE(SUM(agg.total_sales), 0) AS daily_sales
                    FROM reporting_agent_day agg
                    WHERE {" AND ".join(clauses)}
                    GROUP BY agg.sale_date
                )
                SELECT
                    EXTRACT(DAY FROM sale_date)::INT AS day,
                    SUM(daily_sales) OVER (ORDER BY sale_date) AS cumulative_sales
                FROM daily
                ORDER BY sale_date
                """,
                *params,
            )

    async def _fetch_contribution(self, scope: AnalyticsScope, period: str) -> Sequence[asyncpg.Record]:
        clauses, params = self._scope_sql(scope, period)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT
                    agg.firma,
                    COALESCE(SUM(agg.total_sales), 0) AS total_sales
                FROM reporting_agent_day agg
                WHERE {" AND ".join(clauses)}
                GROUP BY agg.firma
                ORDER BY total_sales DESC
                """,
                *params,
            )

    async def _fetch_performance(self, scope: AnalyticsScope, period: str) -> Sequence[asyncpg.Record]:
        clauses, params = self._scope_sql(scope, period)
        target_source = self._target_source_sql(scope, params)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH performance AS (
                    SELECT
                        agg.site_code,
                        MAX(agg.locatie) AS locatie,
                        MAX(agg.firma) AS firma,
                        MAX(agg.regional) AS regional,
                        COALESCE(SUM(agg.total_sales), 0) AS total_sales
                    FROM reporting_agent_day agg
                    WHERE {" AND ".join(clauses)}
                    GROUP BY agg.site_code
                ),
                targets AS (
                    {target_source}
                )
                SELECT
                    performance.site_code,
                    performance.locatie,
                    performance.firma,
                    performance.regional,
                    performance.total_sales,
                    COALESCE(targets.target_value, 0) AS target_value
                FROM performance
                LEFT JOIN targets USING (site_code)
                ORDER BY performance.total_sales ASC
                LIMIT 50
                """,
                *params,
            )

    @staticmethod
    def _target_source_sql(scope: AnalyticsScope, params: list[Any]) -> str:
        if scope.agent:
            params.append(list(scope.agent))
            return f"""
                SELECT site_code, COALESCE(SUM(target_value), 0) AS target_value
                FROM agent_targets
                WHERE import_month = $1
                  AND agent = ANY(${len(params)}::text[])
                GROUP BY site_code
            """
        return """
            SELECT site_code, COALESCE(SUM(target_value), 0) AS target_value
            FROM store_targets
            WHERE import_month = $1
            GROUP BY site_code
        """

    @staticmethod
    def _scope_sql(scope: AnalyticsScope, period: str) -> tuple[list[str], list[Any]]:
        clauses = ["agg.import_month = $1", "agg.locatie NOT ILIKE 'TR %'"]
        params: list[Any] = [period]

        def add(column: str, value: Any, cast: str = "") -> None:
            params.append(value)
            clauses.append(f"{column} = ${len(params)}{cast}")

        def add_many(column: str, values: tuple[str, ...]) -> None:
            params.append(list(values))
            clauses.append(f"{column} = ANY(${len(params)}::text[])")

        if scope.stores:
            params.append(list(scope.stores))
            clauses.append(f"agg.site_code = ANY(${len(params)}::text[])")
        else:
            if scope.firm:
                add("agg.firma", scope.firm)
            if scope.regional:
                add_many("agg.regional", scope.regional)
            if scope.asm:
                add("agg.asm", scope.asm)
        if scope.agent:
            add_many("agg.agent", scope.agent)
        return clauses, params

    @staticmethod
    def _cumulative_by_day(rows: Sequence[asyncpg.Record]) -> dict[int, Decimal]:
        return {int(row["day"]): _money(row["cumulative_sales"]) for row in rows if row["day"] is not None}

    @staticmethod
    def _contribution_view(rows: Sequence[asyncpg.Record], total_sales: Decimal) -> list[DimensionShare]:
        if total_sales <= 0:
            return []
        return [
            DimensionShare(
                id=str(row["firma"]).lower(),
                label=str(row["firma"]),
                value=_money(row["total_sales"]),
                share_pct=_percent(_money(row["total_sales"]) * Decimal("100") / total_sales),
            )
            for row in rows
        ]

    @staticmethod
    def _performance_view(rows: Sequence[asyncpg.Record], comparison_sales: dict[str, Decimal]) -> list[PerformanceRow]:
        result: list[PerformanceRow] = []
        for row in rows:
            site_code = str(row["site_code"])
            sales = _money(row["total_sales"])
            target = _money(row["target_value"])
            progress = _ratio(sales, target)
            result.append(
                PerformanceRow(
                    id=site_code,
                    label=str(row["locatie"]),
                    context=f"{row['firma']} · {row['regional']}",
                    sales=sales,
                    target=target,
                    progress_pct=progress,
                    delta_pct=_delta(sales, comparison_sales.get(site_code, Decimal(0))),
                    risk=_risk(progress),
                )
            )
        return sorted(
            result,
            key=lambda item: item.progress_pct if item.progress_pct is not None else Decimal(-1),
        )[:12]

    @staticmethod
    def _alerts(
        forecast_progress: Decimal | None,
        performance: list[PerformanceRow],
        cutoff_day: int,
    ) -> list[InsightAlert]:
        alerts: list[InsightAlert] = []
        if cutoff_day == 0:
            alerts.append(
                InsightAlert(
                    id="coverage-missing",
                    severity=AlertSeverity.CRITICAL,
                    title="Lipsă acoperire",
                    description="Snapshotul selectat nu conține o dată de vânzare.",
                )
            )
        if forecast_progress is not None and forecast_progress < Decimal("95"):
            alerts.append(
                InsightAlert(
                    id="forecast-gap",
                    severity=(AlertSeverity.CRITICAL if forecast_progress < Decimal("85") else AlertSeverity.WARNING),
                    title="Forecast sub target",
                    description=f"Run-rate-ul liniar indică {forecast_progress}% din target.",
                )
            )
        for row in performance:
            if row.risk is RiskLevel.RISK:
                alerts.append(
                    InsightAlert(
                        id=f"store-risk-{row.id}",
                        severity=AlertSeverity.WARNING,
                        title="Magazin sub ritmul necesar",
                        description=f"Realizarea curentă este {row.progress_pct}%.",
                        entity_label=row.label,
                    )
                )
            if len(alerts) >= 5:
                break
        if not alerts:
            alerts.append(
                InsightAlert(
                    id="scope-healthy",
                    severity=AlertSeverity.INFO,
                    title="Fără abateri majore",
                    description="Regulile inițiale nu indică un risc major în scope-ul curent.",
                )
            )
        return alerts
