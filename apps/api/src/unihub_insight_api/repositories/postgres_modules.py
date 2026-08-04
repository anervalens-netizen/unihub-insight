from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from unihub_insight_api.domain import (
    AlertSeverity,
    AnalyticsScope,
    BreakdownRow,
    Capability,
    ChartKind,
    DataMode,
    DimensionShare,
    InsightAlert,
    KpiMetric,
    MatrixCell,
    MetricUnit,
    ModuleAnalyticsResponse,
    ModuleId,
    OverviewMeta,
    RiskLevel,
    TrendPoint,
    ValueAxis,
)
from unihub_insight_api.repositories.postgres import (
    PostgresAnalyticsRepository,
    _delta,
    _money,
    _percent,
    _ratio,
    _risk,
)
from unihub_insight_api.services import previous_period, scope_label


MODULE_DEFINITIONS: dict[ModuleId, tuple[str, str, Capability, tuple[ValueAxis, ...], tuple[ChartKind, ...]]] = {
    ModuleId.SALES: (
        "Sales Intelligence",
        "Pace, trend, mix și calitatea tranzacțiilor.",
        Capability.ANALYTICS,
        (
            ValueAxis(key="primary", label="Vânzări", unit=MetricUnit.CURRENCY),
            ValueAxis(key="secondary", label="Cantitate", unit=MetricUnit.INTEGER),
            ValueAxis(key="tertiary", label="Bonuri", unit=MetricUnit.INTEGER),
        ),
        (ChartKind.LINE, ChartKind.AREA, ChartKind.BAR, ChartKind.DONUT, ChartKind.TABLE),
    ),
    ModuleId.PERFORMANCE: (
        "Performance",
        "Target, stabilitate și prioritizare pe structură comercială.",
        Capability.ANALYTICS,
        (
            ValueAxis(key="primary", label="Realizare target", unit=MetricUnit.PERCENT),
            ValueAxis(key="secondary", label="Vânzări", unit=MetricUnit.CURRENCY),
            ValueAxis(key="tertiary", label="Productivitate", unit=MetricUnit.CURRENCY),
        ),
        (ChartKind.BAR, ChartKind.HEATMAP, ChartKind.SCATTER, ChartKind.TABLE),
    ),
    ModuleId.CAMPAIGNS: (
        "Campaigns",
        "Focus și mecanisme comerciale peste aceeași sursă de adevăr.",
        Capability.ANALYTICS,
        (
            ValueAxis(key="primary", label="Vânzări Focus", unit=MetricUnit.CURRENCY),
            ValueAxis(key="secondary", label="Cantitate Focus", unit=MetricUnit.INTEGER),
            ValueAxis(key="tertiary", label="Pondere Focus", unit=MetricUnit.PERCENT),
        ),
        (ChartKind.LINE, ChartKind.BAR, ChartKind.DONUT, ChartKind.HEATMAP, ChartKind.TABLE),
    ),
    ModuleId.WORKFORCE: (
        "Workforce",
        "Headcount, stabilitate, acoperire, productivitate și Grile.",
        Capability.MANAGEMENT,
        (
            ValueAxis(key="primary", label="Headcount", unit=MetricUnit.INTEGER),
            ValueAxis(key="secondary", label="Productivitate", unit=MetricUnit.CURRENCY),
            ValueAxis(key="tertiary", label="Acoperire", unit=MetricUnit.PERCENT),
        ),
        (ChartKind.LINE, ChartKind.BAR, ChartKind.HEATMAP, ChartKind.TABLE),
    ),
    ModuleId.COMPENSATION: (
        "Compensation",
        "Cost salarial, distribuție și relația cu performanța.",
        Capability.HR,
        (
            ValueAxis(key="primary", label="Cost salarial", unit=MetricUnit.CURRENCY),
            ValueAxis(key="secondary", label="Salariu mediu", unit=MetricUnit.CURRENCY),
            ValueAxis(key="tertiary", label="Cost / vânzări", unit=MetricUnit.PERCENT),
        ),
        (ChartKind.LINE, ChartKind.BAR, ChartKind.DONUT, ChartKind.SCATTER, ChartKind.TABLE),
    ),
    ModuleId.FINANCE: (
        "Finance & P&L",
        "Venit, cost, profit, marjă și reconciliere actual/estimat.",
        Capability.PNL,
        (
            ValueAxis(key="primary", label="Venit net", unit=MetricUnit.CURRENCY),
            ValueAxis(key="secondary", label="EBIT", unit=MetricUnit.CURRENCY),
            ValueAxis(key="tertiary", label="Marjă EBIT", unit=MetricUnit.PERCENT),
        ),
        (ChartKind.LINE, ChartKind.BAR, ChartKind.WATERFALL, ChartKind.DONUT, ChartKind.TABLE),
    ),
    ModuleId.PLANNING: (
        "Planning",
        "Forecast, target, acuratețe și scenarii comerciale.",
        Capability.MANAGEMENT,
        (
            ValueAxis(key="primary", label="Forecast", unit=MetricUnit.CURRENCY),
            ValueAxis(key="secondary", label="Actual / target", unit=MetricUnit.CURRENCY),
            ValueAxis(key="tertiary", label="Acuratețe", unit=MetricUnit.PERCENT),
        ),
        (ChartKind.LINE, ChartKind.AREA, ChartKind.BAR, ChartKind.SCATTER, ChartKind.TABLE),
    ),
}


REVENUE_CODES = {"v1", "v11", "v2", "v3"}
COGS_CODES = {"c1", "c11", "c2"}
OPERATING_CODES = {"c3", "c4", "c5", "c6"}
CATEGORY_LABELS = {
    "v1": "Venit accesorii",
    "v11": "Alte venituri",
    "v2": "Venit servicii",
    "v3": "Venit operațional",
    "c1": "Cost marfă",
    "c11": "Alte costuri marfă",
    "c2": "Cost direct",
    "c3": "Salarii",
    "c4": "Chirii",
    "c5": "Servicii",
    "c6": "Alte costuri operaționale",
    "a1": "Amortizare",
}


def shift_month(period: str, offset: int) -> str:
    year, month = (int(part) for part in period.split("-"))
    absolute = year * 12 + month - 1 + offset
    next_year, zero_month = divmod(absolute, 12)
    return f"{next_year:04d}-{zero_month + 1:02d}"


def append_reporting_scope(
    scope: AnalyticsScope,
    *,
    alias: str,
    params: list[Any],
    include_agent: bool = True,
) -> list[str]:
    clauses = [f"{alias}.locatie NOT ILIKE 'TR %'"]

    def add(column: str, value: Any, cast: str = "") -> None:
        params.append(value)
        clauses.append(f"{alias}.{column} = ${len(params)}{cast}")

    if scope.stores:
        params.append(list(scope.stores))
        clauses.append(f"{alias}.site_code = ANY(${len(params)}::text[])")
    else:
        if scope.firm:
            add("firma", scope.firm)
        if scope.regional:
            add("regional", scope.regional)
        if scope.asm:
            add("asm", scope.asm)
    if include_agent and scope.agent:
        add("agent", scope.agent)
    return clauses


def finance_metrics(amounts: dict[str, Decimal]) -> dict[str, Decimal]:
    revenue = sum((amounts.get(code, Decimal(0)) for code in REVENUE_CODES), Decimal(0))
    cogs = sum((amounts.get(code, Decimal(0)) for code in COGS_CODES), Decimal(0))
    operating = sum((amounts.get(code, Decimal(0)) for code in OPERATING_CODES), Decimal(0))
    depreciation = amounts.get("a1", Decimal(0))
    gross_margin = revenue - cogs
    ebitda = gross_margin - operating
    ebit = ebitda - depreciation
    return {
        "revenue": _money(revenue),
        "cogs": _money(cogs),
        "gross_margin": _money(gross_margin),
        "operating_costs": _money(operating),
        "ebitda": _money(ebitda),
        "depreciation": _money(depreciation),
        "ebit": _money(ebit),
    }


def shares(items: Sequence[tuple[str, Decimal]]) -> list[DimensionShare]:
    positive = [(label, _money(value)) for label, value in items if value > 0]
    total = sum((value for _, value in positive), Decimal(0))
    if total <= 0:
        return []
    return [
        DimensionShare(
            id=f"share-{index}",
            label=label,
            value=value,
            share_pct=_percent(value * Decimal("100") / total),
        )
        for index, (label, value) in enumerate(positive)
    ]


def standard_deviation(values: Sequence[Decimal]) -> Decimal:
    if len(values) < 2:
        return Decimal(0)
    floats = [float(value) for value in values]
    mean = sum(floats) / len(floats)
    variance = sum((value - mean) ** 2 for value in floats) / len(floats)
    return _percent(math.sqrt(variance))


class PostgresInsightRepository(PostgresAnalyticsRepository):
    async def get_module(
        self,
        module: ModuleId,
        scope: AnalyticsScope,
    ) -> ModuleAnalyticsResponse:
        dispatch = {
            ModuleId.SALES: self._sales,
            ModuleId.PERFORMANCE: self._performance,
            ModuleId.CAMPAIGNS: self._campaigns,
            ModuleId.WORKFORCE: self._workforce,
            ModuleId.COMPENSATION: self._compensation,
            ModuleId.FINANCE: self._finance,
            ModuleId.PLANNING: self._planning,
        }
        return await dispatch[module](scope)

    async def _meta(self, module: ModuleId, scope: AnalyticsScope, source: str) -> OverviewMeta:
        summary = await self._fetch_summary(scope, scope.period)
        as_of = summary["last_sale_date"]
        return OverviewMeta(
            period=scope.period,
            comparison=scope.comparison,
            as_of=as_of if isinstance(as_of, date) else None,
            is_final=bool(summary["is_month_final"]),
            data_mode=DataMode.POSTGRES,
            scope_label=scope_label(scope),
            generated_at=datetime.now(UTC),
            source=source,
        )

    @staticmethod
    def _response(
        module: ModuleId,
        meta: OverviewMeta,
        *,
        kpis: list[KpiMetric],
        trend: list[TrendPoint],
        distribution: list[DimensionShare],
        breakdown: list[BreakdownRow],
        matrix: list[MatrixCell],
        alerts: list[InsightAlert],
    ) -> ModuleAnalyticsResponse:
        title, description, capability, axes, charts = MODULE_DEFINITIONS[module]
        return ModuleAnalyticsResponse(
            meta=meta,
            module=module,
            title=title,
            description=description,
            required_capability=capability,
            axes=axes,
            supported_charts=charts,
            kpis=kpis,
            trend=trend,
            distribution=distribution,
            breakdown=breakdown,
            matrix=matrix,
            alerts=alerts,
        )

    async def _sales_history(
        self,
        scope: AnalyticsScope,
        *,
        start: str,
        end: str,
    ) -> Sequence[asyncpg.Record]:
        params: list[Any] = [start, end]
        clauses = ["agg.import_month BETWEEN $1 AND $2"]
        clauses.extend(append_reporting_scope(scope, alias="agg", params=params))
        if scope.agent:
            params.append(scope.agent)
            target_cte = f"""
                SELECT import_month, site_code, SUM(target_value) AS target_value
                FROM agent_targets
                WHERE import_month BETWEEN $1 AND $2
                  AND agent = ${len(params)}
                GROUP BY import_month, site_code
            """
        else:
            target_cte = """
                SELECT import_month, site_code, SUM(target_value) AS target_value
                FROM store_targets
                WHERE import_month BETWEEN $1 AND $2
                GROUP BY import_month, site_code
            """
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH scoped AS (
                    SELECT
                        agg.import_month,
                        agg.site_code,
                        MAX(agg.locatie) AS locatie,
                        MAX(agg.firma) AS firma,
                        MAX(agg.regional) AS regional,
                        MAX(agg.asm) AS asm,
                        SUM(agg.total_sales) AS total_sales,
                        SUM(agg.total_quantity)::INT AS total_quantity,
                        SUM(agg.receipt_count)::INT AS receipt_count,
                        SUM(agg.receipt_2plus_count)::INT AS receipt_2plus_count,
                        SUM(agg.working_days)::INT AS agent_working_days,
                        MAX(agg.working_days)::INT AS active_days,
                        COUNT(DISTINCT agg.agent)::INT AS agent_count
                    FROM reporting_agent_month agg
                    WHERE {' AND '.join(clauses)}
                    GROUP BY agg.import_month, agg.site_code
                ), targets AS (
                    {target_cte}
                )
                SELECT scoped.*, COALESCE(targets.target_value, 0) AS target_value
                FROM scoped
                LEFT JOIN targets USING (import_month, site_code)
                ORDER BY scoped.import_month, scoped.site_code
                """,
                *params,
            )

    async def _category_distribution(
        self,
        scope: AnalyticsScope,
    ) -> Sequence[asyncpg.Record]:
        params: list[Any] = [scope.period]
        clauses = ["agg.import_month = $1"]
        clauses.extend(append_reporting_scope(scope, alias="agg", params=params))
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT agg.category AS label,
                       SUM(agg.total_sales) AS value
                FROM reporting_category_month agg
                WHERE {' AND '.join(clauses)}
                GROUP BY agg.category
                ORDER BY value DESC
                LIMIT 10
                """,
                *params,
            )

    @staticmethod
    def _store_breakdown(rows: Sequence[asyncpg.Record]) -> list[BreakdownRow]:
        result: list[BreakdownRow] = []
        for row in rows:
            sales = _money(row["total_sales"])
            target = _money(row["target_value"])
            progress = _ratio(sales, target)
            productivity = _money(sales / Decimal(max(int(row["agent_working_days"] or 0), 1)))
            result.append(
                BreakdownRow(
                    id=str(row["site_code"]),
                    label=str(row["locatie"]),
                    context=f"{row['firma']} · {row['regional']} · {row['asm']}",
                    primary=sales,
                    secondary=target,
                    tertiary=productivity,
                    progress_pct=progress,
                    risk=_risk(progress),
                )
            )
        return sorted(
            result,
            key=lambda row: row.progress_pct if row.progress_pct is not None else Decimal(-1),
        )

    @staticmethod
    def _store_matrix(rows: Sequence[asyncpg.Record], periods: set[str]) -> list[MatrixCell]:
        by_store_total: dict[str, Decimal] = defaultdict(Decimal)
        for row in rows:
            if str(row["import_month"]) in periods:
                by_store_total[str(row["site_code"])] += _money(row["total_sales"])
        selected = {
            code for code, _ in sorted(by_store_total.items(), key=lambda item: item[1], reverse=True)[:8]
        }
        result: list[MatrixCell] = []
        for row in rows:
            period = str(row["import_month"])
            code = str(row["site_code"])
            if period not in periods or code not in selected:
                continue
            progress = _ratio(_money(row["total_sales"]), _money(row["target_value"]))
            result.append(
                MatrixCell(
                    x=period,
                    y=str(row["locatie"]),
                    value=progress or Decimal(0),
                    label=f"{progress}%" if progress is not None else "Fără target",
                    risk=_risk(progress),
                )
            )
        return result

    async def _sales(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        start = shift_month(scope.period, -23)
        history, categories, meta = await asyncio.gather(
            self._sales_history(scope, start=start, end=scope.period),
            self._category_distribution(scope),
            self._meta(ModuleId.SALES, scope, "reporting_agent_month/reporting_category_month"),
        )
        current = [row for row in history if str(row["import_month"]) == scope.period]
        total_sales = sum((_money(row["total_sales"]) for row in current), Decimal(0))
        total_target = sum((_money(row["target_value"]) for row in current), Decimal(0))
        total_receipts = sum((Decimal(int(row["receipt_count"] or 0)) for row in current), Decimal(0))
        total_qty = sum((Decimal(int(row["total_quantity"] or 0)) for row in current), Decimal(0))
        receipt_2plus = sum((Decimal(int(row["receipt_2plus_count"] or 0)) for row in current), Decimal(0))
        progress = _ratio(total_sales, total_target)
        previous_key = previous_period(scope.period, scope.comparison)
        previous_sales = sum(
            (_money(row["total_sales"]) for row in history if str(row["import_month"]) == previous_key),
            Decimal(0),
        )
        month_totals: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"sales": Decimal(0), "target": Decimal(0), "qty": Decimal(0), "receipts": Decimal(0)}
        )
        for row in history:
            item = month_totals[str(row["import_month"])]
            item["sales"] += _money(row["total_sales"])
            item["target"] += _money(row["target_value"])
            item["qty"] += Decimal(int(row["total_quantity"] or 0))
            item["receipts"] += Decimal(int(row["receipt_count"] or 0))
        trend: list[TrendPoint] = []
        for period in [shift_month(scope.period, offset) for offset in range(-11, 1)]:
            values = month_totals.get(period)
            if values is None:
                continue
            reference = previous_period(period, scope.comparison)
            comparison = month_totals.get(reference or "", {}).get("sales")
            trend.append(
                TrendPoint(
                    key=period,
                    label=period,
                    primary=_money(values["sales"]),
                    comparison=_money(comparison) if comparison is not None else None,
                    target=_money(values["target"]),
                    secondary=_money(values["qty"]),
                )
            )
        breakdown = self._store_breakdown(current)
        matrix_periods = {shift_month(scope.period, offset) for offset in range(-5, 1)}
        alerts = self._performance_alerts(breakdown)
        if not current:
            alerts.insert(0, self._missing_alert(ModuleId.SALES, "Nu există vânzări pentru perioada și scope-ul selectat."))
        average_receipt = _money(total_sales / total_receipts) if total_receipts > 0 else Decimal(0)
        kpis = [
            KpiMetric(id="sales.total", label="Vânzări", value=_money(total_sales), unit=MetricUnit.CURRENCY, delta_pct=_delta(total_sales, previous_sales), risk=_risk(progress)),
            KpiMetric(id="target.progress_pct", label="Realizare target", value=progress or Decimal(0), unit=MetricUnit.PERCENT, supporting_value=_money(total_target), supporting_label="Target", risk=_risk(progress)),
            KpiMetric(id="receipts.average_value", label="Valoare medie bon", value=average_receipt, unit=MetricUnit.CURRENCY, supporting_value=total_receipts, supporting_label="Bonuri"),
            KpiMetric(id="receipt_2plus_pct", label="Bonuri 2+", value=_ratio(receipt_2plus, total_receipts) or Decimal(0), unit=MetricUnit.PERCENT, supporting_value=total_qty, supporting_label="Cantitate netă"),
        ] if current else []
        return self._response(
            ModuleId.SALES,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares([(str(row["label"]), _money(row["value"])) for row in categories]),
            breakdown=breakdown,
            matrix=self._store_matrix(history, matrix_periods),
            alerts=alerts,
        )

    async def _performance(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        start = shift_month(scope.period, -11)
        history, meta = await asyncio.gather(
            self._sales_history(scope, start=start, end=scope.period),
            self._meta(ModuleId.PERFORMANCE, scope, "reporting_agent_month/store_targets"),
        )
        current = [row for row in history if str(row["import_month"]) == scope.period]
        breakdown = self._store_breakdown(current)
        progresses = [row.progress_pct for row in breakdown if row.progress_pct is not None]
        at_target = sum(1 for value in progresses if value >= Decimal("100"))
        total_sales = sum((_money(row["total_sales"]) for row in current), Decimal(0))
        total_target = sum((_money(row["target_value"]) for row in current), Decimal(0))
        total_agent_days = sum((Decimal(int(row["agent_working_days"] or 0)) for row in current), Decimal(0))
        monthly: dict[str, tuple[Decimal, Decimal]] = defaultdict(lambda: (Decimal(0), Decimal(0)))
        for row in history:
            period = str(row["import_month"])
            sales, target = monthly[period]
            monthly[period] = (sales + _money(row["total_sales"]), target + _money(row["target_value"]))
        trend = [
            TrendPoint(
                key=period,
                label=period,
                primary=_ratio(values[0], values[1]),
                comparison=None,
                target=Decimal("100"),
                secondary=_money(values[0]),
            )
            for period, values in sorted(monthly.items())
        ]
        bands = [
            ("La target", Decimal(sum(1 for value in progresses if value >= Decimal("100")))),
            ("Aproape", Decimal(sum(1 for value in progresses if Decimal("90") <= value < Decimal("100")))),
            ("Sub ritm", Decimal(sum(1 for value in progresses if value < Decimal("90")))),
            ("Fără target", Decimal(len(breakdown) - len(progresses))),
        ]
        network_progress = _ratio(total_sales, total_target)
        kpis = [
            KpiMetric(id="performance.average", label="Realizare rețea", value=network_progress or Decimal(0), unit=MetricUnit.PERCENT, risk=_risk(network_progress)),
            KpiMetric(id="performance.at_target", label="Magazine la target", value=Decimal(at_target), unit=MetricUnit.INTEGER, supporting_value=Decimal(len(breakdown)), supporting_label="Magazine analizate"),
            KpiMetric(id="performance.volatility", label="Volatilitate", value=standard_deviation(progresses), unit=MetricUnit.PERCENT, risk=RiskLevel.WATCH),
            KpiMetric(id="performance.daily_productivity", label="Productivitate / zi-agent", value=_money(total_sales / total_agent_days) if total_agent_days > 0 else Decimal(0), unit=MetricUnit.CURRENCY),
        ] if current else []
        alerts = self._performance_alerts(breakdown)
        if not current:
            alerts.insert(0, self._missing_alert(ModuleId.PERFORMANCE, "Nu există performanță pentru perioada selectată."))
        return self._response(
            ModuleId.PERFORMANCE,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares(bands),
            breakdown=breakdown,
            matrix=self._store_matrix(history, {shift_month(scope.period, offset) for offset in range(-5, 1)}),
            alerts=alerts,
        )

    async def _campaign_rows(
        self,
        scope: AnalyticsScope,
        *,
        start: str,
        end: str,
    ) -> Sequence[asyncpg.Record]:
        params: list[Any] = [start, end]
        focus_clauses = ["focus.import_month BETWEEN $1 AND $2"]
        focus_clauses.extend(append_reporting_scope(scope, alias="focus", params=params))
        total_params = list(params)
        total_clauses = ["tot.import_month BETWEEN $1 AND $2"]
        total_clauses.extend(append_reporting_scope(scope, alias="tot", params=total_params))
        if total_params != params:
            # Both aliases receive the same scope values in the same order.
            params = total_params
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH focus AS (
                    SELECT focus.import_month, focus.site_code,
                           MAX(focus.locatie) AS locatie,
                           MAX(focus.firma) AS firma,
                           MAX(focus.regional) AS regional,
                           MAX(focus.asm) AS asm,
                           SUM(focus.total_sales) AS focus_sales,
                           SUM(focus.total_quantity)::INT AS focus_qty,
                           COUNT(DISTINCT focus.item_code)::INT AS active_products
                    FROM reporting_focus_item_month focus
                    WHERE {' AND '.join(focus_clauses)}
                    GROUP BY focus.import_month, focus.site_code
                ), totals AS (
                    SELECT tot.import_month, tot.site_code,
                           SUM(tot.total_quantity)::INT AS total_qty
                    FROM reporting_agent_month tot
                    WHERE {' AND '.join(total_clauses)}
                    GROUP BY tot.import_month, tot.site_code
                )
                SELECT focus.*, COALESCE(totals.total_qty, 0)::INT AS total_qty
                FROM focus
                LEFT JOIN totals USING (import_month, site_code)
                ORDER BY focus.import_month, focus.site_code
                """,
                *params,
            )

    async def _campaign_distribution(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        params: list[Any] = [scope.period]
        clauses = ["agg.import_month = $1"]
        clauses.extend(append_reporting_scope(scope, alias="agg", params=params))
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT agg.focus_subcategory AS label,
                       SUM(agg.total_sales) AS sales,
                       SUM(agg.total_quantity)::INT AS quantity
                FROM reporting_focus_item_month agg
                WHERE {' AND '.join(clauses)}
                GROUP BY agg.focus_subcategory
                ORDER BY sales DESC
                LIMIT 10
                """,
                *params,
            )

    async def _campaigns(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        start = shift_month(scope.period, -11)
        rows, distribution_rows, meta = await asyncio.gather(
            self._campaign_rows(scope, start=start, end=scope.period),
            self._campaign_distribution(scope),
            self._meta(ModuleId.CAMPAIGNS, scope, "reporting_focus_item_month"),
        )
        current = [row for row in rows if str(row["import_month"]) == scope.period]
        focus_sales = sum((_money(row["focus_sales"]) for row in current), Decimal(0))
        focus_qty = sum((Decimal(int(row["focus_qty"] or 0)) for row in current), Decimal(0))
        total_qty = sum((Decimal(int(row["total_qty"] or 0)) for row in current), Decimal(0))
        active_products = max((int(row["active_products"] or 0) for row in current), default=0)
        monthly: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"sales": Decimal(0), "focus": Decimal(0), "total": Decimal(0)})
        for row in rows:
            item = monthly[str(row["import_month"])]
            item["sales"] += _money(row["focus_sales"])
            item["focus"] += Decimal(int(row["focus_qty"] or 0))
            item["total"] += Decimal(int(row["total_qty"] or 0))
        trend = [
            TrendPoint(
                key=period,
                label=period,
                primary=_money(values["sales"]),
                secondary=_ratio(values["focus"], values["total"]),
            )
            for period, values in sorted(monthly.items())
        ]
        breakdown: list[BreakdownRow] = []
        for row in current:
            share = _ratio(Decimal(int(row["focus_qty"] or 0)), Decimal(int(row["total_qty"] or 0)))
            breakdown.append(
                BreakdownRow(
                    id=str(row["site_code"]),
                    label=str(row["locatie"]),
                    context=f"{row['firma']} · {row['regional']}",
                    primary=_money(row["focus_sales"]),
                    secondary=Decimal(int(row["focus_qty"] or 0)),
                    tertiary=Decimal(int(row["active_products"] or 0)),
                    progress_pct=share,
                    risk=RiskLevel.HEALTHY if share is not None and share >= Decimal("20") else RiskLevel.WATCH,
                )
            )
        top_codes = {row.id for row in sorted(breakdown, key=lambda item: item.primary, reverse=True)[:8]}
        matrix = [
            MatrixCell(
                x=str(row["import_month"]),
                y=str(row["locatie"]),
                value=_ratio(Decimal(int(row["focus_qty"] or 0)), Decimal(int(row["total_qty"] or 0))) or Decimal(0),
                risk=RiskLevel.HEALTHY,
            )
            for row in rows
            if str(row["site_code"]) in top_codes and str(row["import_month"]) >= shift_month(scope.period, -5)
        ]
        alerts: list[InsightAlert] = []
        inactive = [row for row in breakdown if row.primary <= 0]
        if inactive:
            alerts.append(InsightAlert(id="campaign-inactive", severity=AlertSeverity.WARNING, title="Magazine fără adopție", description=f"{len(inactive)} magazine nu au rezultat Focus în scope."))
        if not current:
            alerts.append(self._missing_alert(ModuleId.CAMPAIGNS, "Nu există date Focus materializate pentru perioada selectată."))
        kpis = [
            KpiMetric(id="campaigns.focus_sales", label="Vânzări Focus", value=_money(focus_sales), unit=MetricUnit.CURRENCY),
            KpiMetric(id="campaigns.focus_share", label="Pondere Focus", value=_ratio(focus_qty, total_qty) or Decimal(0), unit=MetricUnit.PERCENT),
            KpiMetric(id="campaigns.active_stores", label="Magazine active", value=Decimal(sum(1 for row in current if _money(row["focus_sales"]) > 0)), unit=MetricUnit.INTEGER),
            KpiMetric(id="campaigns.active_products", label="Produse active", value=Decimal(active_products), unit=MetricUnit.INTEGER),
        ] if current else []
        return self._response(
            ModuleId.CAMPAIGNS,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares([(str(row["label"]), _money(row["sales"])) for row in distribution_rows]),
            breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
            matrix=matrix,
            alerts=alerts,
        )

    async def _workforce_rows(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        start = shift_month(scope.period, -11)
        params: list[Any] = [start, scope.period]
        clauses = ["agg.import_month BETWEEN $1 AND $2"]
        clauses.extend(append_reporting_scope(scope, alias="agg", params=params))
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT agg.import_month, agg.agent,
                       MAX(agg.site_code) AS site_code,
                       MAX(agg.locatie) AS locatie,
                       MAX(agg.firma) AS firma,
                       MAX(agg.regional) AS regional,
                       MAX(agg.asm) AS asm,
                       SUM(agg.total_sales) AS total_sales,
                       SUM(agg.working_days)::INT AS working_days,
                       COUNT(DISTINCT agg.site_code)::INT AS store_count,
                       MIN(profile.first_seen_month) AS first_seen_month,
                       MAX(profile.active_months_count)::INT AS active_months_count,
                       BOOL_OR(COALESCE(life.is_new, false)) AS is_new,
                       BOOL_OR(COALESCE(life.is_reactivated, false)) AS is_reactivated
                FROM reporting_agent_month agg
                LEFT JOIN reporting_agent_profile profile ON profile.agent = agg.agent
                LEFT JOIN reporting_agent_lifecycle_month life
                  ON life.import_month = agg.import_month AND life.agent = agg.agent
                WHERE {' AND '.join(clauses)}
                GROUP BY agg.import_month, agg.agent
                ORDER BY agg.import_month, agg.agent
                """,
                *params,
            )

    async def _grile_alerts(self, scope: AnalyticsScope) -> list[InsightAlert]:
        params: list[Any] = [scope.period]
        clauses = ["status.run_month = $1"]
        if scope.stores:
            params.append(list(scope.stores))
            clauses.append(f"status.site_code = ANY(${len(params)}::text[])")
        else:
            if scope.firm:
                params.append(scope.firm)
                clauses.append(f"store.firma = ${len(params)}")
            if scope.regional:
                params.append(scope.regional)
                clauses.append(f"store.regional = ${len(params)}")
            if scope.asm:
                params.append(scope.asm)
                clauses.append(f"store.asm = ${len(params)}")
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                f"""
                SELECT COUNT(*)::INT AS total,
                       COUNT(*) FILTER (WHERE status.fill_status <> 'ok' OR status.target_status <> 'ok' OR status.sales_status <> 'ok')::INT AS problems,
                       COUNT(*) FILTER (WHERE status.last_error_code IS NOT NULL)::INT AS errors
                FROM grile_store_current_status status
                JOIN stores store ON store.site_code = status.site_code
                WHERE {' AND '.join(clauses)}
                """,
                *params,
            )
        if row is None or int(row["total"] or 0) == 0:
            return [InsightAlert(id="grile-missing", severity=AlertSeverity.INFO, title="Grile fără observație", description="Nu există observații Grile pentru scope și perioadă.")]
        alerts: list[InsightAlert] = []
        if int(row["problems"] or 0) > 0:
            alerts.append(InsightAlert(id="grile-problems", severity=AlertSeverity.WARNING, title="Grile cu neconcordanțe", description=f"{row['problems']} magazine au cel puțin o verificare diferită de OK."))
        if int(row["errors"] or 0) > 0:
            alerts.append(InsightAlert(id="grile-errors", severity=AlertSeverity.CRITICAL, title="Erori Grile", description=f"{row['errors']} magazine păstrează o ultimă eroare de verificare."))
        return alerts

    async def _workforce(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        rows, grile_alerts, meta = await asyncio.gather(
            self._workforce_rows(scope),
            self._grile_alerts(scope),
            self._meta(ModuleId.WORKFORCE, scope, "reporting_agent_month/reporting_agent_profile/grile"),
        )
        current = [row for row in rows if str(row["import_month"]) == scope.period]
        headcount = len(current)
        total_sales = sum((_money(row["total_sales"]) for row in current), Decimal(0))
        staffed_stores = {str(row["site_code"]) for row in current}
        selected_store_count = len(scope.stores) if scope.stores else len(staffed_stores)
        movement_count = sum(1 for row in current if row["is_new"] or row["is_reactivated"])
        stability = _percent(Decimal(max(headcount - movement_count, 0)) * Decimal("100") / Decimal(headcount)) if headcount else None
        coverage = _percent(Decimal(len(staffed_stores)) * Decimal("100") / Decimal(selected_store_count)) if selected_store_count else None
        monthly: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"headcount": Decimal(0), "sales": Decimal(0), "new": Decimal(0)})
        for row in rows:
            item = monthly[str(row["import_month"])]
            item["headcount"] += 1
            item["sales"] += _money(row["total_sales"])
            item["new"] += Decimal(1 if row["is_new"] or row["is_reactivated"] else 0)
        trend = [
            TrendPoint(
                key=period,
                label=period,
                primary=values["headcount"],
                secondary=_money(values["sales"] / values["headcount"]) if values["headcount"] > 0 else None,
                comparison=values["new"],
            )
            for period, values in sorted(monthly.items())
        ]
        tenure_bands: dict[str, Decimal] = defaultdict(Decimal)
        breakdown: list[BreakdownRow] = []
        for row in current:
            months = int(row["active_months_count"] or 0)
            band = "< 3 luni" if months < 3 else "3–12 luni" if months < 12 else "1–3 ani" if months < 36 else "3+ ani"
            tenure_bands[band] += 1
            sales = _money(row["total_sales"])
            days = Decimal(max(int(row["working_days"] or 0), 1))
            breakdown.append(
                BreakdownRow(
                    id=f"{row['site_code']}:{row['agent']}",
                    label=str(row["agent"]),
                    context=f"{row['locatie']} · {row['regional']}",
                    primary=sales,
                    secondary=_money(sales / days),
                    tertiary=Decimal(months),
                    progress_pct=None,
                    risk=RiskLevel.WATCH if row["is_new"] or row["is_reactivated"] else RiskLevel.HEALTHY,
                )
            )
        top_agents = {row.id for row in sorted(breakdown, key=lambda item: item.primary, reverse=True)[:8]}
        matrix = [
            MatrixCell(
                x=str(row["import_month"]),
                y=str(row["agent"]),
                value=_money(_money(row["total_sales"]) / Decimal(max(int(row["working_days"] or 0), 1))),
                risk=RiskLevel.HEALTHY,
            )
            for row in rows
            if f"{row['site_code']}:{row['agent']}" in top_agents and str(row["import_month"]) >= shift_month(scope.period, -5)
        ]
        alerts = list(grile_alerts)
        if not current:
            alerts.insert(0, self._missing_alert(ModuleId.WORKFORCE, "Nu există agenți activi în scope-ul selectat."))
        kpis = [
            KpiMetric(id="workforce.headcount", label="Headcount activ", value=Decimal(headcount), unit=MetricUnit.INTEGER),
            KpiMetric(id="workforce.productivity", label="Productivitate / agent", value=_money(total_sales / Decimal(headcount)) if headcount else Decimal(0), unit=MetricUnit.CURRENCY),
            KpiMetric(id="workforce.coverage", label="Acoperire magazine", value=coverage or Decimal(0), unit=MetricUnit.PERCENT, risk=_risk(coverage)),
            KpiMetric(id="workforce.stability", label="Stabilitate", value=stability or Decimal(0), unit=MetricUnit.PERCENT, risk=_risk(stability)),
        ] if current else []
        return self._response(ModuleId.WORKFORCE, meta, kpis=kpis, trend=trend, distribution=shares(list(tenure_bands.items())), breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True), matrix=matrix, alerts=alerts)

    @staticmethod
    def _salary_scope(scope: AnalyticsScope, params: list[Any], alias: str = "salary") -> list[str]:
        clauses: list[str] = []
        if scope.stores:
            params.append(list(scope.stores))
            clauses.append(f"{alias}.site_code = ANY(${len(params)}::text[])")
        else:
            if scope.firm:
                params.append(scope.firm)
                clauses.append(f"LOWER({alias}.company_name) = LOWER(${len(params)})")
            if scope.regional:
                params.append(scope.regional)
                clauses.append(f"EXISTS (SELECT 1 FROM stores org WHERE org.site_code = {alias}.site_code AND org.regional = ${len(params)})")
            if scope.asm:
                params.append(scope.asm)
                clauses.append(f"EXISTS (SELECT 1 FROM stores org WHERE org.site_code = {alias}.site_code AND org.asm = ${len(params)})")
        if scope.agent:
            params.append(scope.agent)
            clauses.append(f"EXISTS (SELECT 1 FROM agent_salary_links link WHERE link.person_id = {alias}.person_id AND link.agent_code = ${len(params)} AND link.match_status = 'confirmed')")
        return clauses

    async def _salary_rows(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        start = shift_month(scope.period, -11)
        start_year, start_month = (int(part) for part in start.split("-"))
        end_year, end_month = (int(part) for part in scope.period.split("-"))
        params: list[Any] = [start_year * 100 + start_month, end_year * 100 + end_month]
        clauses = ["salary.year * 100 + salary.month BETWEEN $1 AND $2"]
        clauses.extend(self._salary_scope(scope, params))
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT salary.year, salary.month, salary.person_id,
                       MAX(salary.full_name) AS full_name,
                       MAX(salary.company_name) AS company_name,
                       MAX(salary.site_code) AS site_code,
                       MAX(salary.locatie) AS locatie,
                       SUM(salary.total_salary) AS total_salary
                FROM salary_records salary
                WHERE {' AND '.join(clauses)}
                GROUP BY salary.year, salary.month, salary.person_id
                ORDER BY salary.year, salary.month, full_name
                """,
                *params,
            )

    async def _compensation(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        salary_rows, sales_rows, meta = await asyncio.gather(
            self._salary_rows(scope),
            self._sales_history(scope, start=shift_month(scope.period, -11), end=scope.period),
            self._meta(ModuleId.COMPENSATION, scope, "salary_records/reporting_agent_month"),
        )
        current_year, current_month = (int(part) for part in scope.period.split("-"))
        current = [row for row in salary_rows if int(row["year"]) == current_year and int(row["month"]) == current_month]
        payroll = sum((_money(row["total_salary"]) for row in current), Decimal(0))
        salaries = sorted((_money(row["total_salary"]) for row in current))
        average = _money(payroll / Decimal(len(salaries))) if salaries else Decimal(0)
        if salaries:
            middle = len(salaries) // 2
            median = salaries[middle] if len(salaries) % 2 else _money((salaries[middle - 1] + salaries[middle]) / Decimal(2))
        else:
            median = Decimal(0)
        sales = sum((_money(row["total_sales"]) for row in sales_rows if str(row["import_month"]) == scope.period), Decimal(0))
        ratio = _ratio(payroll, sales)
        monthly: dict[str, list[Decimal]] = defaultdict(list)
        companies: dict[str, Decimal] = defaultdict(Decimal)
        for row in salary_rows:
            period = f"{int(row['year']):04d}-{int(row['month']):02d}"
            monthly[period].append(_money(row["total_salary"]))
            if period == scope.period:
                companies[str(row["company_name"])] += _money(row["total_salary"])
        trend = []
        for period, values in sorted(monthly.items()):
            total = sum(values, Decimal(0))
            trend.append(TrendPoint(key=period, label=period, primary=_money(total), secondary=_money(total / Decimal(len(values))) if values else None))
        breakdown = [
            BreakdownRow(
                id=str(row["person_id"]),
                label=str(row["full_name"]),
                context=f"{row['company_name']} · {row['locatie'] or row['site_code']}",
                primary=_money(row["total_salary"]),
                secondary=None,
                tertiary=None,
                risk=RiskLevel.HEALTHY,
            )
            for row in current
        ]
        top_people = {row.id for row in sorted(breakdown, key=lambda item: item.primary, reverse=True)[:8]}
        matrix = [
            MatrixCell(x=f"{int(row['year']):04d}-{int(row['month']):02d}", y=str(row["full_name"]), value=_money(row["total_salary"]), risk=RiskLevel.HEALTHY)
            for row in salary_rows
            if str(row["person_id"]) in top_people and f"{int(row['year']):04d}-{int(row['month']):02d}" >= shift_month(scope.period, -5)
        ]
        alerts: list[InsightAlert] = []
        if len(current) < 3 and current:
            alerts.append(InsightAlert(id="salary-narrow-scope", severity=AlertSeverity.WARNING, title="Scope salarial foarte restrâns", description="Rezultatul conține mai puțin de trei persoane; exportul agregat trebuie suprimat în producție."))
        if not current:
            alerts.append(self._missing_alert(ModuleId.COMPENSATION, "Nu există date salariale pentru perioada selectată."))
        kpis = [
            KpiMetric(id="compensation.payroll", label="Cost salarial", value=_money(payroll), unit=MetricUnit.CURRENCY),
            KpiMetric(id="compensation.average", label="Salariu mediu", value=average, unit=MetricUnit.CURRENCY),
            KpiMetric(id="compensation.median", label="Salariu median", value=median, unit=MetricUnit.CURRENCY),
            KpiMetric(id="compensation.sales_ratio", label="Cost / vânzări", value=ratio or Decimal(0), unit=MetricUnit.PERCENT, risk=RiskLevel.WATCH if ratio and ratio > Decimal("25") else RiskLevel.HEALTHY),
        ] if current else []
        return self._response(ModuleId.COMPENSATION, meta, kpis=kpis, trend=trend, distribution=shares(list(companies.items())), breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True), matrix=matrix, alerts=alerts)

    async def _finance_rows(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        start = shift_month(scope.period, -11)
        params: list[Any] = [date.fromisoformat(f"{start}-01"), date.fromisoformat(f"{scope.period}-01")]
        filters: list[str] = []
        if scope.stores:
            params.append(list(scope.stores))
            filters.append(f"(row.linked_site_code = ANY(${len(params)}::text[]) OR (row.linked_site_code IS NULL AND row.source_site_code = ANY(${len(params)}::text[])))")
        else:
            if scope.firm:
                params.append(scope.firm)
                filters.append(f"LOWER(row.company_name) = LOWER(${len(params)})")
            if scope.regional:
                params.append(scope.regional)
                filters.append(f"row.regional = ${len(params)}")
            if scope.asm:
                params.append(scope.asm)
                filters.append(f"row.asm = ${len(params)}")
        filter_sql = " AND ".join(filters) if filters else "TRUE"
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH normalized AS (
                    SELECT pnl.company_name, pnl.period, pnl.source_site_code,
                           pnl.source_location_name, pnl.category_code, pnl.amount,
                           pnl.data_kind,
                           CASE WHEN pnl.source_site_code = '__FINANCE_UNALLOCATED__'
                                THEN pnl.source_site_code
                                ELSE COALESCE(link.site_code, pnl.source_site_code) END AS canonical_site_code,
                           CASE WHEN pnl.source_site_code = '__FINANCE_UNALLOCATED__'
                                THEN NULL ELSE link.site_code END AS linked_site_code,
                           COALESCE(store.regional, 'Nealocat') AS regional,
                           COALESCE(store.asm, 'Nealocat') AS asm
                    FROM store_pnl_monthly pnl
                    LEFT JOIN store_pnl_site_links link
                      ON link.company_name = pnl.company_name
                     AND link.source_site_code = pnl.source_site_code
                    LEFT JOIN stores store
                      ON store.site_code = CASE WHEN pnl.source_site_code = '__FINANCE_UNALLOCATED__'
                          THEN NULL ELSE COALESCE(link.site_code, pnl.source_site_code) END
                    WHERE pnl.period BETWEEN $1 AND $2
                ), preferred_kind AS (
                    SELECT company_name, period, canonical_site_code,
                           CASE WHEN BOOL_OR(data_kind = 'actual') THEN 'actual' ELSE 'estimated' END AS data_kind
                    FROM normalized
                    GROUP BY company_name, period, canonical_site_code
                )
                SELECT row.*
                FROM normalized row
                JOIN preferred_kind preferred
                  ON preferred.company_name = row.company_name
                 AND preferred.period = row.period
                 AND preferred.canonical_site_code = row.canonical_site_code
                 AND preferred.data_kind = row.data_kind
                WHERE {filter_sql}
                ORDER BY row.period, row.company_name, row.canonical_site_code, row.category_code
                """,
                *params,
            )

    async def _finance(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        rows, meta = await asyncio.gather(
            self._finance_rows(scope),
            self._meta(ModuleId.FINANCE, scope, "store_pnl_monthly"),
        )
        monthly_amounts: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        monthly_estimate: dict[str, bool] = defaultdict(bool)
        store_amounts: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        store_labels: dict[tuple[str, str], tuple[str, str]] = {}
        category_current: dict[str, Decimal] = defaultdict(Decimal)
        for row in rows:
            period = row["period"].strftime("%Y-%m")
            category = str(row["category_code"])
            amount = _money(row["amount"])
            monthly_amounts[period][category] += amount
            monthly_estimate[period] |= str(row["data_kind"]) == "estimated"
            if period == scope.period:
                category_current[category] += amount
            if str(row["source_site_code"]) == "__FINANCE_UNALLOCATED__":
                continue
            key = (str(row["company_name"]), str(row["canonical_site_code"]))
            store_amounts[key][category] += amount
            store_labels[key] = (str(row["source_location_name"]), str(row["regional"]))
        current_metrics = finance_metrics(monthly_amounts.get(scope.period, {}))
        margin = _ratio(current_metrics["ebit"], current_metrics["revenue"])
        trend = []
        for period, amounts in sorted(monthly_amounts.items()):
            values = finance_metrics(amounts)
            trend.append(TrendPoint(key=period, label=period, primary=values["revenue"], secondary=values["ebit"], target=_ratio(values["ebit"], values["revenue"]), is_estimate=monthly_estimate[period]))
        breakdown: list[BreakdownRow] = []
        for key, amounts in store_amounts.items():
            values = finance_metrics(amounts)
            label, regional = store_labels[key]
            store_margin = _ratio(values["ebit"], values["revenue"])
            breakdown.append(BreakdownRow(id=f"{key[0]}:{key[1]}", label=label, context=f"{key[0]} · {regional}", primary=values["revenue"], secondary=values["ebit"], tertiary=values["operating_costs"], progress_pct=store_margin, risk=RiskLevel.RISK if values["ebit"] < 0 else RiskLevel.HEALTHY))
        top_stores = {item.id for item in sorted(breakdown, key=lambda item: item.primary, reverse=True)[:8]}
        matrix: list[MatrixCell] = []
        by_store_month: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for row in rows:
            if str(row["source_site_code"]) == "__FINANCE_UNALLOCATED__":
                continue
            period = row["period"].strftime("%Y-%m")
            identifier = f"{row['company_name']}:{row['canonical_site_code']}"
            if identifier in top_stores and period >= shift_month(scope.period, -5):
                by_store_month[(identifier, period)][str(row["category_code"])] += _money(row["amount"])
        label_by_id = {item.id: item.label for item in breakdown}
        for (identifier, period), amounts in by_store_month.items():
            values = finance_metrics(amounts)
            store_margin = _ratio(values["ebit"], values["revenue"])
            matrix.append(MatrixCell(x=period, y=label_by_id[identifier], value=store_margin or Decimal(0), risk=RiskLevel.RISK if values["ebit"] < 0 else RiskLevel.HEALTHY))
        cost_items = [(CATEGORY_LABELS.get(code, code), amount) for code, amount in category_current.items() if code in COGS_CODES | OPERATING_CODES | {"a1"}]
        alerts: list[InsightAlert] = []
        negative = [item for item in breakdown if item.secondary is not None and item.secondary < 0]
        if negative:
            alerts.append(InsightAlert(id="finance-negative", severity=AlertSeverity.CRITICAL, title="Magazine cu EBIT negativ", description=f"{len(negative)} magazine au EBIT negativ în intervalul analizat."))
        if monthly_estimate.get(scope.period):
            alerts.append(InsightAlert(id="finance-estimate", severity=AlertSeverity.WARNING, title="Perioadă estimată", description="Cel puțin o componentă P&L este estimată; actualele au prioritate unde există."))
        if not rows:
            alerts.append(self._missing_alert(ModuleId.FINANCE, "Nu există date P&L pentru scope-ul selectat."))
        kpis = [
            KpiMetric(id="finance.revenue", label="Venit net", value=current_metrics["revenue"], unit=MetricUnit.CURRENCY),
            KpiMetric(id="finance.ebit", label="EBIT", value=current_metrics["ebit"], unit=MetricUnit.CURRENCY, risk=RiskLevel.RISK if current_metrics["ebit"] < 0 else RiskLevel.HEALTHY),
            KpiMetric(id="finance.ebit_margin", label="Marjă EBIT", value=margin or Decimal(0), unit=MetricUnit.PERCENT, risk=RiskLevel.RISK if current_metrics["ebit"] < 0 else RiskLevel.HEALTHY),
            KpiMetric(id="finance.operating_costs", label="Cost operațional", value=current_metrics["operating_costs"], unit=MetricUnit.CURRENCY),
        ] if rows else []
        return self._response(ModuleId.FINANCE, meta, kpis=kpis, trend=trend, distribution=shares(cost_items), breakdown=sorted(breakdown, key=lambda item: item.secondary or Decimal(0)), matrix=matrix, alerts=alerts)

    async def _planning_rows(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        params: list[Any] = [shift_month(scope.period, -11), scope.period]
        clauses: list[str] = ["run.forecast_month BETWEEN $1 AND $2", "run.status = 'completed'", "run.metric = 'sales_value'"]
        scope_params: list[Any] = params
        store_clauses = append_reporting_scope(scope, alias="store", params=scope_params, include_agent=False)
        clauses.extend(store_clauses)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH selected_runs AS (
                    SELECT DISTINCT ON (forecast_month)
                           id, forecast_month
                    FROM ai_forecast_runs run
                    WHERE run.forecast_month BETWEEN $1 AND $2
                      AND run.status = 'completed'
                      AND run.metric = 'sales_value'
                      AND run.horizon IN ('current_month', 'rolling_12m')
                    ORDER BY forecast_month,
                             CASE WHEN horizon = 'rolling_12m' THEN 0 ELSE 1 END,
                             generated_at DESC, id DESC
                ), forecast AS (
                    SELECT selected.forecast_month, forecast.site_code,
                           store.locatie, store.firma, store.regional, store.asm,
                           forecast.forecast_sales
                    FROM selected_runs selected
                    JOIN ai_forecast_store_month forecast ON forecast.run_id = selected.id
                    JOIN stores store ON store.site_code = forecast.site_code
                    WHERE {' AND '.join(store_clauses)}
                ), actual AS (
                    SELECT agg.import_month, agg.site_code, SUM(agg.total_sales) AS actual_sales
                    FROM reporting_agent_month agg
                    WHERE agg.import_month BETWEEN $1 AND $2
                    GROUP BY agg.import_month, agg.site_code
                )
                SELECT forecast.*, actual.actual_sales,
                       COALESCE(target.target_value, 0) AS target_value
                FROM forecast
                LEFT JOIN actual
                  ON actual.import_month = forecast.forecast_month
                 AND actual.site_code = forecast.site_code
                LEFT JOIN store_targets target
                  ON target.import_month = forecast.forecast_month
                 AND target.site_code = forecast.site_code
                ORDER BY forecast.forecast_month, forecast.forecast_sales DESC
                """,
                *scope_params,
            )

    async def _planning(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        rows, meta = await asyncio.gather(
            self._planning_rows(scope),
            self._meta(ModuleId.PLANNING, scope, "ai_forecast_runs/ai_forecast_store_month"),
        )
        current = [row for row in rows if str(row["forecast_month"]) == scope.period]
        forecast = sum((_money(row["forecast_sales"]) for row in current), Decimal(0))
        target = sum((_money(row["target_value"]) for row in current), Decimal(0))
        actual = sum((_money(row["actual_sales"]) for row in current if row["actual_sales"] is not None), Decimal(0))
        monthly: dict[str, dict[str, Decimal | bool]] = defaultdict(lambda: {"forecast": Decimal(0), "actual": Decimal(0), "target": Decimal(0), "has_actual": False})
        for row in rows:
            item = monthly[str(row["forecast_month"])]
            item["forecast"] = Decimal(item["forecast"]) + _money(row["forecast_sales"])
            item["target"] = Decimal(item["target"]) + _money(row["target_value"])
            if row["actual_sales"] is not None:
                item["actual"] = Decimal(item["actual"]) + _money(row["actual_sales"])
                item["has_actual"] = True
        trend: list[TrendPoint] = []
        accuracies: list[Decimal] = []
        for period, values in sorted(monthly.items()):
            forecast_value = _money(values["forecast"])
            actual_value = _money(values["actual"]) if bool(values["has_actual"]) else None
            if actual_value is not None and actual_value > 0:
                error = abs(forecast_value - actual_value) / actual_value * Decimal("100")
                accuracies.append(max(Decimal(0), _percent(Decimal("100") - error)))
            trend.append(TrendPoint(key=period, label=period, primary=forecast_value, comparison=actual_value, target=_money(values["target"]), is_estimate=actual_value is None))
        accuracy = _percent(sum(accuracies, Decimal(0)) / Decimal(len(accuracies))) if accuracies else None
        breakdown: list[BreakdownRow] = []
        for row in current:
            forecast_value = _money(row["forecast_sales"])
            target_value = _money(row["target_value"])
            actual_value = _money(row["actual_sales"]) if row["actual_sales"] is not None else None
            progress = _ratio(forecast_value, target_value)
            breakdown.append(BreakdownRow(id=str(row["site_code"]), label=str(row["locatie"]), context=f"{row['firma']} · {row['regional']}", primary=forecast_value, secondary=actual_value, tertiary=target_value, progress_pct=progress, delta_pct=_delta(forecast_value, actual_value) if actual_value is not None else None, risk=_risk(progress)))
        distribution_by_regional: dict[str, Decimal] = defaultdict(Decimal)
        for row in current:
            distribution_by_regional[str(row["regional"])] += _money(row["forecast_sales"])
        top_codes = {item.id for item in sorted(breakdown, key=lambda item: item.primary, reverse=True)[:8]}
        matrix = [
            MatrixCell(x=str(row["forecast_month"]), y=str(row["locatie"]), value=_ratio(_money(row["forecast_sales"]), _money(row["actual_sales"])) or Decimal(0), risk=RiskLevel.HEALTHY)
            for row in rows
            if str(row["site_code"]) in top_codes and str(row["forecast_month"]) >= shift_month(scope.period, -5) and row["actual_sales"] is not None
        ]
        alerts: list[InsightAlert] = []
        if not current:
            alerts.append(self._missing_alert(ModuleId.PLANNING, "Nu există un forecast complet pentru perioada și scope-ul selectat."))
        elif target > 0 and forecast < target:
            alerts.append(InsightAlert(id="planning-gap", severity=AlertSeverity.WARNING, title="Forecast sub target", description=f"Gap-ul proiectat este {_money(forecast - target)} RON."))
        kpis = [
            KpiMetric(id="planning.forecast", label="Forecast", value=_money(forecast), unit=MetricUnit.CURRENCY, supporting_value=_money(target), supporting_label="Target", risk=_risk(_ratio(forecast, target))),
            KpiMetric(id="planning.target_gap", label="Gap față de target", value=_money(forecast - target), unit=MetricUnit.CURRENCY, risk=_risk(_ratio(forecast, target))),
            KpiMetric(id="planning.accuracy", label="Acuratețe istorică", value=accuracy or Decimal(0), unit=MetricUnit.PERCENT, risk=_risk(accuracy)),
            KpiMetric(id="planning.actual", label="Actual disponibil", value=_money(actual), unit=MetricUnit.CURRENCY),
        ] if current else []
        return self._response(ModuleId.PLANNING, meta, kpis=kpis, trend=trend, distribution=shares(list(distribution_by_regional.items())), breakdown=sorted(breakdown, key=lambda item: item.progress_pct or Decimal(0)), matrix=matrix, alerts=alerts)

    @staticmethod
    def _performance_alerts(rows: Sequence[BreakdownRow]) -> list[InsightAlert]:
        alerts: list[InsightAlert] = []
        for row in rows:
            if row.risk is RiskLevel.RISK:
                alerts.append(InsightAlert(id=f"risk-{row.id}", severity=AlertSeverity.WARNING, title="Entitate sub ritmul necesar", description=f"Realizarea curentă este {row.progress_pct}%.", entity_label=row.label))
            if len(alerts) >= 5:
                break
        if not alerts and rows:
            alerts.append(InsightAlert(id="scope-healthy", severity=AlertSeverity.INFO, title="Fără abateri majore", description="Nicio entitate nu a intrat în pragul critic curent."))
        return alerts

    @staticmethod
    def _missing_alert(module: ModuleId, description: str) -> InsightAlert:
        return InsightAlert(id=f"{module.value}-missing", severity=AlertSeverity.CRITICAL, title="Date indisponibile", description=description)
