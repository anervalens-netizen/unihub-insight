from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from unihub_insight_api.domain import (
    AlertSeverity,
    AnalyticsScope,
    BreakdownRow,
    CalendarCell,
    Capability,
    ChartKind,
    DataMode,
    DimensionShare,
    InsightAlert,
    KpiMetric,
    MatrixCell,
    MetricUnit,
    ModuleAnalyticsResponse,
    ModuleAnalyticsSlice,
    ModuleId,
    OverviewMeta,
    RiskLevel,
    SourceDomain,
    SourceMetadata,
    SourceStatus,
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
        (
            ChartKind.LINE,
            ChartKind.AREA,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.CALENDAR,
            ChartKind.TABLE,
        ),
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
        (
            ChartKind.BAR,
            ChartKind.HEATMAP,
            ChartKind.SCATTER,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        ),
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
        (ChartKind.LINE, ChartKind.BAR, ChartKind.DONUT, ChartKind.TREEMAP, ChartKind.HEATMAP, ChartKind.TABLE),
    ),
    ModuleId.WORKFORCE: (
        "Workforce",
        "Activitate comercială observată, productivitate și Grile; nu reprezintă registru oficial de personal.",
        Capability.MANAGEMENT,
        (
            ValueAxis(key="primary", label="Headcount", unit=MetricUnit.INTEGER),
            ValueAxis(key="secondary", label="Productivitate", unit=MetricUnit.CURRENCY),
            ValueAxis(key="tertiary", label="Acoperire", unit=MetricUnit.PERCENT),
        ),
        (
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.TREEMAP,
            ChartKind.HEATMAP,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        ),
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
        (
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.SCATTER,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        ),
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
        (
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.WATERFALL,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.TABLE,
        ),
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

MODULE_SOURCE_DOMAINS: dict[ModuleId, SourceDomain] = {
    ModuleId.SALES: SourceDomain.SALES,
    ModuleId.PERFORMANCE: SourceDomain.SALES,
    ModuleId.CAMPAIGNS: SourceDomain.CAMPAIGNS,
    ModuleId.WORKFORCE: SourceDomain.WORKFORCE,
    ModuleId.COMPENSATION: SourceDomain.COMPENSATION,
    ModuleId.FINANCE: SourceDomain.FINANCE,
    ModuleId.PLANNING: SourceDomain.PLANNING,
}


REVENUE_CODES = {"v1", "v11", "v2", "v3"}
COGS_CODES = {"c1", "c11", "c2"}
OPERATING_CODES = {"c3", "c4", "c5", "c6"}
MIN_COMPENSATION_POPULATION = 3
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


async def _empty_records() -> Sequence[asyncpg.Record]:
    return ()


def compensation_is_suppressed(person_count: int) -> bool:
    return 0 < person_count < MIN_COMPENSATION_POPULATION


def filter_visible_compensation_rows(rows: Sequence[Any]) -> list[Any]:
    return [row for row in rows if not compensation_is_suppressed(int(row["eligible_person_count"]))]


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

    def add_many(column: str, values: tuple[str, ...]) -> None:
        params.append(list(values))
        clauses.append(f"{alias}.{column} = ANY(${len(params)}::text[])")

    if scope.stores:
        params.append(list(scope.stores))
        clauses.append(f"{alias}.site_code = ANY(${len(params)}::text[])")
    else:
        if scope.firm:
            add("firma", scope.firm)
        if scope.regional:
            add_many("regional", scope.regional)
        if scope.asm:
            add("asm", scope.asm)
    if include_agent and scope.agent:
        add_many("agent", scope.agent)
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

    async def _meta(
        self,
        module: ModuleId,
        scope: AnalyticsScope,
        source: str,
        additional_domains: tuple[SourceDomain, ...] = (),
    ) -> OverviewMeta:
        snapshot = await self.resolve_snapshot(scope)
        domain = MODULE_SOURCE_DOMAINS[module]
        source_meta = snapshot.sources.get(domain.value)
        domains = (domain, *additional_domains)
        return OverviewMeta(
            period=scope.period,
            comparison=scope.comparison,
            as_of=source_meta.as_of if source_meta else None,
            is_final=source_meta.is_final if source_meta else False,
            data_mode=DataMode.POSTGRES,
            scope_label=scope_label(scope),
            generated_at=datetime.now(UTC),
            source=source_meta.source if source_meta else source,
            analytical_snapshot_id=snapshot.id,
            snapshot_contract_version=snapshot.contract_version,
            sources={item: metadata for item in domains if (metadata := snapshot.sources.get(item.value)) is not None},
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
        calendar: list[CalendarCell] | None = None,
        alerts: list[InsightAlert],
        visits: ModuleAnalyticsSlice | None = None,
        campaigns: dict[str, ModuleAnalyticsSlice] | None = None,
        portfolio: dict[str, ModuleAnalyticsSlice] | None = None,
        subviews: dict[str, ModuleAnalyticsSlice] | None = None,
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
            calendar=calendar or [],
            alerts=alerts,
            visits=visits,
            campaigns=campaigns or {},
            portfolio=portfolio or {},
            subviews=subviews or {},
        )

    @staticmethod
    def _slice_status(sources: dict[SourceDomain, SourceMetadata]) -> SourceStatus:
        """Derive a slice state only from the immutable snapshot metadata."""
        if not sources or any(item.status is SourceStatus.UNAVAILABLE for item in sources.values()):
            return SourceStatus.UNAVAILABLE
        if any(item.status in {SourceStatus.PARTIAL, SourceStatus.STALE} for item in sources.values()):
            return SourceStatus.PARTIAL
        return SourceStatus.OFFICIAL

    @classmethod
    def _govern_slices(
        cls,
        slices: dict[str, ModuleAnalyticsSlice],
        sources: dict[SourceDomain, SourceMetadata],
    ) -> dict[str, ModuleAnalyticsSlice]:
        status = cls._slice_status(sources)
        return {key: slice_.model_copy(update={"status": status, "sources": sources}) for key, slice_ in slices.items()}

    @classmethod
    def _unavailable_slice(
        cls,
        *,
        source: SourceMetadata | None,
        title: str,
        description: str,
    ) -> ModuleAnalyticsSlice:
        sources = {source.domain: source} if source is not None else {}
        return ModuleAnalyticsSlice(
            status=SourceStatus.UNAVAILABLE,
            sources=sources,
            axes=(),
            supported_charts=(ChartKind.KPI, ChartKind.TABLE),
            kpis=[],
            trend=[],
            distribution=[],
            breakdown=[],
            matrix=[],
            alerts=[
                InsightAlert(
                    id=f"{title.lower().replace(' ', '-')}-unavailable",
                    severity=AlertSeverity.INFO,
                    title=title,
                    description=description,
                )
            ],
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
            params.append(list(scope.agent))
            target_cte = f"""
                SELECT import_month, site_code, SUM(target_value) AS target_value
                FROM agent_targets
                WHERE import_month BETWEEN $1 AND $2
                  AND agent = ANY(${len(params)}::text[])
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
                    WHERE {" AND ".join(clauses)}
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
                WHERE {" AND ".join(clauses)}
                GROUP BY agg.category
                ORDER BY value DESC
                LIMIT 10
                """,
                *params,
            )

    async def _portfolio_category_rows(
        self,
        scope: AnalyticsScope,
        *,
        dimension: str,
    ) -> Sequence[asyncpg.Record]:
        if dimension not in {"category", "subcategory"}:
            raise ValueError(f"Unsupported category portfolio dimension: {dimension}")

        params: list[Any] = [scope.period]
        clauses = ["agg.import_month = $1"]
        clauses.extend(append_reporting_scope(scope, alias="agg", params=params))
        if dimension == "category":
            identifier = "agg.category"
            label = "agg.category"
            context = "'Categorie'"
            grouping = "agg.category"
        else:
            identifier = "CONCAT(agg.category, ':', agg.subcategory)"
            label = "agg.subcategory"
            context = "agg.category"
            grouping = "agg.category, agg.subcategory"
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT
                    {identifier} AS id,
                    {label} AS label,
                    {context} AS context,
                    SUM(agg.total_sales) AS total_sales,
                    SUM(agg.total_quantity)::BIGINT AS net_quantity,
                    NULL::BIGINT AS return_quantity,
                    NULL::BIGINT AS receipt_count,
                    1::INT AS label_variants,
                    1::INT AS attribute_variants
                FROM reporting_category_month agg
                WHERE {" AND ".join(clauses)}
                GROUP BY {grouping}
                ORDER BY ABS(SUM(agg.total_sales)) DESC, id
                LIMIT 5000
                """,
                *params,
            )

    async def _portfolio_item_rows(
        self,
        scope: AnalyticsScope,
        *,
        dimension: str,
    ) -> Sequence[asyncpg.Record]:
        if dimension not in {"brand", "product"}:
            raise ValueError(f"Unsupported item portfolio dimension: {dimension}")

        params: list[Any] = [scope.period]
        clauses = ["item.import_month = $1"]
        clauses.extend(append_reporting_scope(scope, alias="item", params=params))
        if dimension == "brand":
            identifier = "COALESCE(scoped.brand, 'Necunoscut')"
            label = "COALESCE(scoped.brand, 'Necunoscut')"
            context = "'Brand real din Monthly Review'"
            grouping = "COALESCE(scoped.brand, 'Necunoscut')"
        else:
            identifier = "scoped.item_code"
            label = "MAX(scoped.item_name)"
            context = "CONCAT('SKU ', scoped.item_code, ' · ', COALESCE(MAX(scoped.brand), 'Necunoscut'), ' · ', COALESCE(MAX(scoped.category), 'Necategorizat'))"
            grouping = "scoped.item_code"
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH attributes AS (
                    SELECT
                        supplement.import_month,
                        supplement.site_code,
                        supplement.agent,
                        supplement.item_code,
                        MAX(NULLIF(BTRIM(supplement.brand), '')) AS brand,
                        MAX(NULLIF(BTRIM(supplement.category), '')) AS category
                    FROM insight.monthly_review_item_month supplement
                    WHERE supplement.import_month = $1
                    GROUP BY supplement.import_month, supplement.site_code, supplement.agent, supplement.item_code
                ), scoped AS (
                    SELECT
                        item.import_month,
                        item.site_code,
                        item.agent,
                        item.item_code,
                        MAX(item.item_name) AS item_name,
                        SUM(item.total_sales) AS total_sales,
                        SUM(item.net_quantity)::BIGINT AS net_quantity,
                        SUM(item.return_quantity)::BIGINT AS return_quantity,
                        SUM(item.receipt_count)::BIGINT AS receipt_count,
                        MAX(attributes.brand) AS brand,
                        MAX(attributes.category) AS category
                    FROM reporting_item_month item
                    LEFT JOIN attributes
                        ON attributes.import_month = item.import_month
                       AND attributes.site_code IS NOT DISTINCT FROM item.site_code
                       AND attributes.agent IS NOT DISTINCT FROM item.agent
                       AND attributes.item_code = item.item_code
                    WHERE {" AND ".join(clauses)}
                    GROUP BY item.import_month, item.site_code, item.agent, item.item_code
                )
                SELECT
                    {identifier} AS id,
                    {label} AS label,
                    {context} AS context,
                    SUM(scoped.total_sales) AS total_sales,
                    SUM(scoped.net_quantity)::BIGINT AS net_quantity,
                    SUM(scoped.return_quantity)::BIGINT AS return_quantity,
                    SUM(scoped.receipt_count)::BIGINT AS receipt_count,
                    COUNT(DISTINCT scoped.item_name)::INT AS label_variants,
                    COUNT(DISTINCT CONCAT(COALESCE(scoped.brand, ''), '|', COALESCE(scoped.category, '')))::INT
                        AS attribute_variants
                FROM scoped
                GROUP BY {grouping}
                ORDER BY ABS(SUM(scoped.total_sales)) DESC, id
                LIMIT 5000
                """,
                *params,
            )

    @staticmethod
    def _portfolio_number(row: Any, key: str) -> Decimal:
        value = row[key]
        return Decimal(str(value)) if value is not None else Decimal(0)

    @classmethod
    def _portfolio_slice(
        cls,
        *,
        dimension: str,
        rows: Sequence[Any],
        item_detail: bool,
        include_receipt_incidence: bool = False,
    ) -> ModuleAnalyticsSlice:
        total_sales = sum((cls._portfolio_number(row, "total_sales") for row in rows), Decimal(0))
        total_quantity = sum((cls._portfolio_number(row, "net_quantity") for row in rows), Decimal(0))
        total_returns = sum((cls._portfolio_number(row, "return_quantity") for row in rows), Decimal(0))
        total_receipts = sum((cls._portfolio_number(row, "receipt_count") for row in rows), Decimal(0))
        positive_sales = sum(
            (
                cls._portfolio_number(row, "total_sales")
                for row in rows
                if cls._portfolio_number(row, "total_sales") > 0
            ),
            Decimal(0),
        )
        distribution = [
            DimensionShare(
                id=str(row["id"]),
                label=str(row["label"]),
                value=_money(cls._portfolio_number(row, "total_sales")),
                share_pct=_percent(cls._portfolio_number(row, "total_sales") * Decimal("100") / positive_sales),
            )
            for row in rows
            if cls._portfolio_number(row, "total_sales") > 0 and positive_sales > 0
        ]
        breakdown = [
            BreakdownRow(
                id=str(row["id"]),
                label=str(row["label"]),
                context=str(row["context"]),
                primary=_money(cls._portfolio_number(row, "total_sales")),
                secondary=cls._portfolio_number(row, "net_quantity"),
                tertiary=cls._portfolio_number(row, "return_quantity") if item_detail else None,
                quaternary=cls._portfolio_number(row, "receipt_count") if include_receipt_incidence else None,
                risk=RiskLevel.HEALTHY,
            )
            for row in rows
        ]
        kpis = [
            KpiMetric(
                id="sales.portfolio_sales",
                label="Vânzări nete",
                value=_money(total_sales),
                unit=MetricUnit.CURRENCY,
            ),
            KpiMetric(
                id="sales.portfolio_net_quantity",
                label="Cantitate netă",
                value=total_quantity,
                unit=MetricUnit.INTEGER,
            ),
        ]
        axes = [
            ValueAxis(key="primary", label="Vânzări nete", unit=MetricUnit.CURRENCY),
            ValueAxis(key="secondary", label="Cantitate netă", unit=MetricUnit.INTEGER),
        ]
        if item_detail:
            kpis.append(
                KpiMetric(
                    id="sales.portfolio_return_quantity",
                    label="Cantitate retur semnată",
                    value=total_returns,
                    unit=MetricUnit.INTEGER,
                )
            )
            axes.append(ValueAxis(key="tertiary", label="Cantitate retur semnată", unit=MetricUnit.INTEGER))
        if include_receipt_incidence:
            kpis.append(
                KpiMetric(
                    id="sales.portfolio_receipt_incidence",
                    label="Incidențe SKU în bonuri",
                    value=total_receipts,
                    unit=MetricUnit.INTEGER,
                )
            )
            axes.append(ValueAxis(key="quaternary", label="Incidențe SKU în bonuri", unit=MetricUnit.INTEGER))
        alerts: list[InsightAlert] = []
        non_positive = sum(1 for row in rows if cls._portfolio_number(row, "total_sales") <= 0)
        if non_positive:
            alerts.append(
                InsightAlert(
                    id=f"portfolio-{dimension}-non-positive-sales",
                    severity=AlertSeverity.INFO,
                    title="Rânduri return-only păstrate în tabel",
                    description=(
                        "Ponderea graficului este calculată numai din vânzări nete pozitive; "
                        "rândurile cu vânzări zero sau negative rămân în tabel și în totalul metricii."
                    ),
                )
            )
        if dimension == "product":
            conflicts = sum(
                1
                for row in rows
                if cls._portfolio_number(row, "label_variants") > 1
                or cls._portfolio_number(row, "attribute_variants") > 1
            )
            if conflicts:
                alerts.append(
                    InsightAlert(
                        id="portfolio-product-identity-conflict",
                        severity=AlertSeverity.INFO,
                        title="SKU cu denumiri sau atribute multiple",
                        description=(
                            f"{conflicts} SKU au variante în sursă; identitatea și totalurile rămân consolidate pe item_code, "
                            "iar eticheta/contextul folosesc MAX stabil."
                        ),
                    )
                )
        supported_charts = (
            (ChartKind.KPI, ChartKind.TABLE)
            if dimension == "product"
            else (ChartKind.KPI, ChartKind.BAR, ChartKind.DONUT, ChartKind.TREEMAP, ChartKind.TABLE)
        )
        return ModuleAnalyticsSlice(
            axes=tuple(axes),
            supported_charts=supported_charts,
            kpis=kpis,
            trend=[],
            distribution=distribution,
            breakdown=breakdown,
            matrix=[],
            alerts=alerts,
            entity_dimension=dimension,
            distribution_dimension=dimension,
        )

    async def _sales_portfolio(self, scope: AnalyticsScope) -> dict[str, ModuleAnalyticsSlice]:
        category_rows, subcategory_rows, brand_rows, product_rows = await asyncio.gather(
            self._portfolio_category_rows(scope, dimension="category"),
            self._portfolio_category_rows(scope, dimension="subcategory"),
            self._portfolio_item_rows(scope, dimension="brand"),
            self._portfolio_item_rows(scope, dimension="product"),
        )
        return {
            "category": self._portfolio_slice(dimension="category", rows=category_rows, item_detail=False),
            "subcategory": self._portfolio_slice(dimension="subcategory", rows=subcategory_rows, item_detail=False),
            "brand": self._portfolio_slice(dimension="brand", rows=brand_rows, item_detail=True),
            "product": self._portfolio_slice(
                dimension="product",
                rows=product_rows,
                item_detail=True,
                include_receipt_incidence=True,
            ),
        }

    async def _sales_calendar(self, scope: AnalyticsScope) -> list[CalendarCell]:
        params: list[Any] = [scope.period]
        clauses = ["daily.period = $1"]
        clauses.extend(append_reporting_scope(scope, alias="daily", params=params))
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                f"""
                SELECT
                    daily.sale_date,
                    SUM(daily.net_sales) AS total_sales,
                    SUM(daily.net_quantity) AS net_quantity,
                    SUM(daily.positive_quantity) AS positive_quantity,
                    SUM(daily.return_quantity) AS return_quantity,
                    SUM(daily.receipt_count) AS receipt_count,
                    SUM(daily.receipt_2plus_count) AS receipt_2plus_count,
                    COUNT(DISTINCT daily.site_code) AS observed_store_count,
                    MIN(daily.coverage_state) AS coverage_state
                FROM reporting_sales_day_v1 AS daily
                WHERE {" AND ".join(clauses)}
                GROUP BY daily.sale_date
                ORDER BY daily.sale_date
                """,
                *params,
            )
        return [
            CalendarCell(
                date=row["sale_date"],
                sales=_money(row["total_sales"]),
                net_quantity=Decimal(int(row["net_quantity"] or 0)),
                positive_quantity=Decimal(int(row["positive_quantity"] or 0)),
                return_quantity=Decimal(int(row["return_quantity"] or 0)),
                receipt_count=Decimal(int(row["receipt_count"] or 0)),
                receipt_2plus_count=Decimal(int(row["receipt_2plus_count"] or 0)),
                observed_store_count=int(row["observed_store_count"]),
                coverage_state=str(row["coverage_state"]),
            )
            for row in rows
        ]

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
        selected = {code for code, _ in sorted(by_store_total.items(), key=lambda item: item[1], reverse=True)[:8]}
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
        history, categories, calendar_rows, meta, portfolio = await asyncio.gather(
            self._sales_history(scope, start=start, end=scope.period),
            self._category_distribution(scope),
            self._sales_calendar(scope),
            self._meta(ModuleId.SALES, scope, "reporting_agent_month/reporting_category_month"),
            self._sales_portfolio(scope),
        )
        sales_source = meta.sources.get(SourceDomain.SALES)
        portfolio = self._govern_slices(
            portfolio,
            {SourceDomain.SALES: sales_source} if sales_source is not None else {},
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
            lambda: {
                "sales": Decimal(0),
                "target": Decimal(0),
                "qty": Decimal(0),
                "receipts": Decimal(0),
            }
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
            alerts.insert(
                0,
                self._missing_alert(ModuleId.SALES, "Nu există vânzări pentru perioada și scope-ul selectat."),
            )
        average_receipt = _money(total_sales / total_receipts) if total_receipts > 0 else Decimal(0)
        kpis = (
            [
                KpiMetric(
                    id="sales.total",
                    label="Vânzări",
                    value=_money(total_sales),
                    unit=MetricUnit.CURRENCY,
                    delta_pct=_delta(total_sales, previous_sales),
                    risk=_risk(progress),
                ),
                KpiMetric(
                    id="target.progress_pct",
                    label="Realizare target",
                    value=progress or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    supporting_value=_money(total_target),
                    supporting_label="Target",
                    risk=_risk(progress),
                ),
                KpiMetric(
                    id="receipts.average_value",
                    label="Valoare medie bon",
                    value=average_receipt,
                    unit=MetricUnit.CURRENCY,
                    supporting_value=total_receipts,
                    supporting_label="Bonuri",
                ),
                KpiMetric(
                    id="receipts.total",
                    label="Bonuri",
                    value=total_receipts,
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="receipt_2plus_pct",
                    label="Bonuri 2+",
                    value=_ratio(receipt_2plus, total_receipts) or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    supporting_value=total_qty,
                    supporting_label="Cantitate netă",
                ),
            ]
            if current
            else []
        )
        return self._response(
            ModuleId.SALES,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares([(str(row["label"]), _money(row["value"])) for row in categories]),
            breakdown=breakdown,
            matrix=self._store_matrix(history, matrix_periods),
            calendar=calendar_rows,
            alerts=alerts,
            portfolio=portfolio,
        )

    async def _visit_rows(
        self,
        scope: AnalyticsScope,
        *,
        start: str,
        end: str,
    ) -> Sequence[asyncpg.Record]:
        params: list[Any] = [start, end]
        clauses = ["visit.period BETWEEN $1 AND $2"]
        clauses.extend(
            append_reporting_scope(
                scope,
                alias="visit",
                params=params,
                include_agent=False,
            )
        )
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT visit.period, visit.team_leader_id, visit.team_leader_name,
                       visit.site_code, visit.locatie, visit.firma, visit.regional,
                       visit.asm, visit.total_visits, visit.avg_completion,
                       visit.avg_duration, visit.distinct_stores,
                       visit.checklist_score, visit.approved_pct
                FROM reporting_visit_month_v2 visit
                WHERE {" AND ".join(clauses)}
                ORDER BY visit.period, visit.team_leader_name, visit.site_code
                """,
                *params,
            )

    @staticmethod
    def _weighted_visit_value(rows: Sequence[asyncpg.Record], field: str) -> Decimal | None:
        weighted = Decimal(0)
        weight = Decimal(0)
        for row in rows:
            value = row[field]
            if value is None:
                continue
            row_weight = Decimal(int(row["total_visits"] or 0))
            weighted += Decimal(str(value)) * row_weight
            weight += row_weight
        return _percent(weighted / weight) if weight > 0 else None

    async def _visit_slice(
        self,
        scope: AnalyticsScope,
        source: SourceMetadata | None = None,
    ) -> ModuleAnalyticsSlice:
        if source is None:
            snapshot = await self.resolve_snapshot(scope)
            source = snapshot.sources.get(SourceDomain.VISITS.value)
        if scope.agent:
            return self._unavailable_slice(
                source=source,
                title="Vizite indisponibile pentru filtrul agent",
                description=(
                    "Vizitele sunt atribuite Team Leader-ului autor; scope-ul agent moștenit "
                    "nu este permis și nu este ignorat."
                ),
            )
        if source is None or source.status is SourceStatus.UNAVAILABLE:
            return self._unavailable_slice(
                source=source,
                title="Vizite indisponibile",
                description="Read-model-ul FieldOps nu este eligibil în snapshotul selectat.",
            )
        rows = await self._visit_rows(
            scope,
            start=shift_month(scope.period, -11),
            end=scope.period,
        )
        current = [row for row in rows if str(row["period"]) == scope.period]
        total_visits = sum((Decimal(int(row["total_visits"] or 0)) for row in current), Decimal(0))
        distinct_stores = len({str(row["site_code"]) for row in current})
        avg_completion = self._weighted_visit_value(current, "avg_completion")
        checklist_score = self._weighted_visit_value(current, "checklist_score")

        monthly_rows: dict[str, list[asyncpg.Record]] = defaultdict(list)
        for row in rows:
            monthly_rows[str(row["period"])].append(row)
        trend = [
            TrendPoint(
                key=period,
                label=period,
                primary=sum(
                    (Decimal(int(row["total_visits"] or 0)) for row in period_rows),
                    Decimal(0),
                ),
                secondary=self._weighted_visit_value(period_rows, "avg_completion"),
            )
            for period, period_rows in sorted(monthly_rows.items())
        ]

        leader_rows: dict[str, list[asyncpg.Record]] = defaultdict(list)
        for row in current:
            leader_rows[str(row["team_leader_id"])].append(row)
        breakdown: list[BreakdownRow] = []
        leader_totals: list[tuple[str, Decimal]] = []
        leader_names: dict[str, str] = {}
        for leader_id, items in leader_rows.items():
            leader_name = str(items[0]["team_leader_name"])
            leader_names[leader_id] = leader_name
            visit_count = sum(
                (Decimal(int(row["total_visits"] or 0)) for row in items),
                Decimal(0),
            )
            store_count = len({str(row["site_code"]) for row in items})
            completion = self._weighted_visit_value(items, "avg_completion")
            checklist = self._weighted_visit_value(items, "checklist_score")
            duration = self._weighted_visit_value(items, "avg_duration")
            leader_totals.append((leader_name, visit_count))
            breakdown.append(
                BreakdownRow(
                    id=leader_id,
                    label=leader_name,
                    context=(f"{store_count} magazine · durată medie {duration if duration is not None else '—'} h"),
                    primary=visit_count,
                    secondary=completion,
                    tertiary=Decimal(store_count),
                    progress_pct=checklist,
                    risk=(
                        RiskLevel.RISK
                        if completion is not None and completion < Decimal("80")
                        else RiskLevel.WATCH
                        if completion is None
                        else RiskLevel.HEALTHY
                    ),
                )
            )
        breakdown.sort(key=lambda item: item.primary, reverse=True)

        top_leaders = {item.id for item in breakdown[:8]} or {str(row["team_leader_id"]) for row in rows}
        matrix_totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        matrix_names: dict[str, str] = dict(leader_names)
        for row in rows:
            leader_id = str(row["team_leader_id"])
            if leader_id not in top_leaders:
                continue
            period = str(row["period"])
            if period < shift_month(scope.period, -5):
                continue
            matrix_totals[(period, leader_id)] += Decimal(int(row["total_visits"] or 0))
            matrix_names[leader_id] = str(row["team_leader_name"])
        matrix = [
            MatrixCell(
                x=period,
                y=matrix_names.get(leader_id, leader_id),
                value=value,
                label="Vizite",
            )
            for (period, leader_id), value in sorted(matrix_totals.items())
        ]

        alerts: list[InsightAlert] = []
        if not current:
            alerts.append(
                InsightAlert(
                    id="visits-missing",
                    severity=AlertSeverity.INFO,
                    title="Vizite neobservate",
                    description="Nu există vizite FieldOps eligibile în scope și perioadă.",
                )
            )
        elif avg_completion is not None and avg_completion < Decimal("80"):
            alerts.append(
                InsightAlert(
                    id="visits-completion-low",
                    severity=AlertSeverity.WARNING,
                    title="Completion vizite sub prag",
                    description=f"Completion mediu este {avg_completion}% în perioada selectată.",
                )
            )
        kpis = (
            [
                KpiMetric(
                    id="visits.total",
                    label="Vizite",
                    value=total_visits,
                    unit=MetricUnit.INTEGER,
                    supporting_value=Decimal(len(leader_rows)),
                    supporting_label="Team Leaders observați",
                ),
                KpiMetric(
                    id="visits.distinct_stores",
                    label="Magazine vizitate",
                    value=Decimal(distinct_stores),
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="visits.avg_completion",
                    label="Completion mediu",
                    value=avg_completion or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=_risk(avg_completion),
                ),
                KpiMetric(
                    id="visits.checklist_score",
                    label="Scor checklist",
                    value=checklist_score or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=_risk(checklist_score),
                ),
            ]
            if current
            else []
        )
        return ModuleAnalyticsSlice(
            status=self._slice_status({SourceDomain.VISITS: source}),
            sources={SourceDomain.VISITS: source},
            axes=(
                ValueAxis(key="primary", label="Vizite", unit=MetricUnit.INTEGER),
                ValueAxis(key="secondary", label="Completion", unit=MetricUnit.PERCENT),
                ValueAxis(key="tertiary", label="Magazine", unit=MetricUnit.INTEGER),
            ),
            supported_charts=(ChartKind.LINE, ChartKind.BAR, ChartKind.HEATMAP, ChartKind.TABLE),
            kpis=kpis,
            trend=trend,
            distribution=shares(leader_totals),
            breakdown=breakdown,
            matrix=matrix,
            alerts=alerts,
        )

    async def _performance(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        start = shift_month(scope.period, -11)
        history, meta, visits = await asyncio.gather(
            self._sales_history(scope, start=start, end=scope.period),
            self._meta(
                ModuleId.PERFORMANCE,
                scope,
                "reporting_agent_month/store_targets",
                (SourceDomain.VISITS,),
            ),
            self._visit_slice(scope),
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
            monthly[period] = (
                sales + _money(row["total_sales"]),
                target + _money(row["target_value"]),
            )
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
            (
                "Aproape",
                Decimal(sum(1 for value in progresses if Decimal("90") <= value < Decimal("100"))),
            ),
            ("Sub ritm", Decimal(sum(1 for value in progresses if value < Decimal("90")))),
            ("Fără target", Decimal(len(breakdown) - len(progresses))),
        ]
        network_progress = _ratio(total_sales, total_target)
        kpis = (
            [
                KpiMetric(
                    id="performance.average",
                    label="Realizare rețea",
                    value=network_progress or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=_risk(network_progress),
                ),
                KpiMetric(
                    id="performance.at_target",
                    label="Magazine la target",
                    value=Decimal(at_target),
                    unit=MetricUnit.INTEGER,
                    supporting_value=Decimal(len(breakdown)),
                    supporting_label="Magazine analizate",
                ),
                KpiMetric(
                    id="performance.volatility",
                    label="Volatilitate",
                    value=standard_deviation(progresses),
                    unit=MetricUnit.PERCENT,
                    risk=RiskLevel.WATCH,
                ),
                KpiMetric(
                    id="performance.daily_productivity",
                    label="Productivitate / zi-agent",
                    value=_money(total_sales / total_agent_days) if total_agent_days > 0 else Decimal(0),
                    unit=MetricUnit.CURRENCY,
                ),
            ]
            if current
            else []
        )
        alerts = self._performance_alerts(breakdown)
        if not current:
            alerts.insert(
                0,
                self._missing_alert(ModuleId.PERFORMANCE, "Nu există performanță pentru perioada selectată."),
            )
        return self._response(
            ModuleId.PERFORMANCE,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares(bands),
            breakdown=breakdown,
            matrix=self._store_matrix(history, {shift_month(scope.period, offset) for offset in range(-5, 1)}),
            alerts=alerts,
            visits=visits,
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
                WITH focus_source AS MATERIALIZED (
                    SELECT focus.*
                    FROM reporting_focus_item_month focus
                    WHERE {" AND ".join(focus_clauses)}
                ), focus AS (
                    SELECT source.import_month, source.site_code,
                           MAX(source.locatie) AS locatie,
                           MAX(source.firma) AS firma,
                           MAX(source.regional) AS regional,
                           MAX(source.asm) AS asm,
                           SUM(source.total_sales) AS focus_sales,
                           SUM(source.total_quantity)::INT AS focus_qty,
                           COUNT(DISTINCT source.item_code)::INT AS active_products
                    FROM focus_source source
                    GROUP BY source.import_month, source.site_code
                ), focus_products AS (
                    SELECT source.import_month,
                           COUNT(DISTINCT source.item_code)::INT AS scope_active_products
                    FROM focus_source source
                    GROUP BY source.import_month
                ), totals AS (
                    SELECT tot.import_month, tot.site_code,
                           SUM(tot.total_quantity)::INT AS total_qty
                    FROM reporting_agent_month tot
                    WHERE {" AND ".join(total_clauses)}
                    GROUP BY tot.import_month, tot.site_code
                )
                SELECT focus.*, focus_products.scope_active_products,
                       COALESCE(totals.total_qty, 0)::INT AS total_qty
                FROM focus
                JOIN focus_products USING (import_month)
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
                WHERE {" AND ".join(clauses)}
                GROUP BY agg.focus_subcategory
                ORDER BY sales DESC
                LIMIT 10
                """,
                *params,
            )

    async def _campaign_mechanism_rows(
        self,
        scope: AnalyticsScope,
        *,
        start: str,
        end: str,
    ) -> Sequence[asyncpg.Record]:
        params: list[Any] = [start, end]
        clauses = ["campaign.period BETWEEN $1 AND $2"]
        clauses.extend(append_reporting_scope(scope, alias="campaign", params=params))
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT campaign.period, campaign.mechanism, campaign.mechanism_variant, campaign.campaign_key,
                       campaign.site_code, campaign.agent, campaign.locatie, campaign.firma,
                       campaign.regional, campaign.asm,
                       campaign.actual_sales, campaign.actual_quantity,
                       campaign.active_product_count, campaign.active_product_codes,
                       campaign.promo_qualifying_bons,
                       campaign.promo_discounted_units,
                       campaign.promo_discount_value,
                       campaign.incentive_sold_quantity,
                       campaign.incentive_eligible_quantity,
                       campaign.incentive_qualified_quantity,
                       campaign.incentive_value,
                       campaign.incentive_potential,
                       campaign.incentive_store_qualified,
                       campaign.status, campaign.warnings
                FROM reporting_campaign_month_v3 AS campaign
                WHERE {" AND ".join(clauses)}
                  AND campaign.mechanism IN ('promo', 'incentive')
                ORDER BY campaign.period, campaign.mechanism,
                         campaign.campaign_key, campaign.site_code
                """,
                *params,
            )

    @staticmethod
    def _commercial_campaign_slice(
        mechanism: str,
        rows: Sequence[asyncpg.Record],
        period: str,
        *,
        source: SourceMetadata | None = None,
        metric_name: str | None = None,
        mechanism_variant: str | None = None,
    ) -> ModuleAnalyticsSlice:
        is_promo = mechanism == "promo"
        metric_name = metric_name or mechanism

        def matches(row: asyncpg.Record) -> bool:
            if str(row["mechanism"]) != mechanism:
                return False
            row_variant = str(row.get("mechanism_variant") or "")
            if mechanism_variant is not None:
                return row_variant == mechanism_variant
            # Folii has its own product surface even though Retail evaluates it
            # under the broader promo mechanism.
            return not (is_promo and row_variant == "same_model_screen_camera")

        all_current = [row for row in rows if str(row["period"]) == period and matches(row)]
        current = [row for row in all_current if str(row["status"]) != "unavailable"]
        mechanism_rows = [row for row in rows if matches(row) and str(row["status"]) != "unavailable"]

        def numeric(row: asyncpg.Record, field: str) -> Decimal:
            value = row[field]
            return Decimal(str(value)) if value is not None else Decimal(0)

        def reward(row: asyncpg.Record) -> Decimal:
            return numeric(row, "promo_discount_value" if is_promo else "incentive_value")

        def volume(row: asyncpg.Record) -> Decimal:
            return numeric(row, "actual_quantity")

        sales = sum((numeric(row, "actual_sales") for row in current), Decimal(0))
        quantity = sum((volume(row) for row in current), Decimal(0))
        reward_value = sum((reward(row) for row in current), Decimal(0))
        active_product_codes = {str(code) for row in current for code in (row["active_product_codes"] or ())}
        active_products = len(active_product_codes)
        if is_promo:
            active_store_codes = {
                str(row["site_code"])
                for row in current
                if numeric(row, "promo_qualifying_bons") > 0
                or numeric(row, "promo_discounted_units") > 0
                or numeric(row, "promo_discount_value") > 0
            }
        else:
            active_store_codes = {
                str(row["site_code"])
                for row in current
                if bool(row["incentive_store_qualified"])
                or numeric(row, "incentive_qualified_quantity") > 0
                or numeric(row, "incentive_value") > 0
            }
        qualifying = sum(
            (numeric(row, "promo_qualifying_bons" if is_promo else "incentive_qualified_quantity") for row in current),
            Decimal(0),
        )
        eligible = sum(
            (numeric(row, "promo_discounted_units" if is_promo else "incentive_eligible_quantity") for row in current),
            Decimal(0),
        )

        prefix = f"campaigns.{metric_name}"
        kpis = []
        if current:
            kpis = [
                KpiMetric(id=f"{prefix}_sales", label="Vânzări", value=_money(sales), unit=MetricUnit.CURRENCY),
                KpiMetric(id=f"{prefix}_quantity", label="Cantitate netă", value=quantity, unit=MetricUnit.INTEGER),
                KpiMetric(
                    id=f"{prefix}_{'discount' if is_promo else 'reward'}",
                    label="Discount" if is_promo else "Bonus / recompensă",
                    value=_money(reward_value),
                    unit=MetricUnit.CURRENCY,
                ),
                KpiMetric(
                    id=f"{prefix}_active_stores",
                    label="Magazine participante",
                    value=Decimal(len(active_store_codes)),
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id=f"{prefix}_active_products",
                    label="Produse participante",
                    value=Decimal(active_products),
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id=f"{prefix}_{'discounted_units' if is_promo else 'eligible_quantity'}",
                    label="Unități cu discount" if is_promo else "Cantitate eligibilă",
                    value=eligible,
                    unit=MetricUnit.INTEGER,
                ),
            ]
            if not is_promo or any(row["promo_qualifying_bons"] is not None for row in current):
                kpis.insert(
                    -1,
                    KpiMetric(
                        id=f"{prefix}_{'qualifying_receipts' if is_promo else 'qualified_quantity'}",
                        label="Bonuri eligibile" if is_promo else "Cantitate calificată",
                        value=qualifying,
                        unit=MetricUnit.INTEGER,
                    ),
                )

        monthly: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"sales": Decimal(0), "reward": Decimal(0)})
        by_campaign: dict[str, Decimal] = defaultdict(Decimal)
        current_by_store: dict[tuple[str, str], dict[str, Any]] = {}
        history_by_store: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in mechanism_rows:
            row_period = str(row["period"])
            campaign_key = str(row["campaign_key"])
            monthly[row_period]["sales"] += numeric(row, "actual_sales")
            monthly[row_period]["reward"] += reward(row)
            if row_period == period:
                by_campaign[str(row["campaign_key"])] += reward(row)
            key = (row_period, campaign_key, str(row["site_code"]))
            bucket = history_by_store.setdefault(
                key,
                {
                    "campaign_key": campaign_key,
                    "site_code": str(row["site_code"]),
                    "locatie": str(row["locatie"] or row["site_code"]),
                    "firma": str(row["firma"] or "—"),
                    "regional": str(row["regional"] or "—"),
                    "sales": Decimal(0),
                    "quantity": Decimal(0),
                    "reward": Decimal(0),
                    "eligible": Decimal(0),
                    "qualifying": Decimal(0),
                    "active_product_codes": set(),
                },
            )
            bucket["sales"] += numeric(row, "actual_sales")
            bucket["quantity"] += volume(row)
            bucket["reward"] += reward(row)
            bucket["eligible"] += numeric(
                row,
                "promo_discounted_units" if is_promo else "incentive_eligible_quantity",
            )
            bucket["qualifying"] += numeric(
                row,
                "promo_qualifying_bons" if is_promo else "incentive_qualified_quantity",
            )
            bucket["active_product_codes"].update(str(code) for code in (row["active_product_codes"] or ()))
            if row_period == period:
                current_by_store[(campaign_key, str(row["site_code"]))] = bucket

        trend = [
            TrendPoint(
                key=key,
                label=key,
                primary=_money(values["sales"]),
                secondary=_money(values["reward"]),
            )
            for key, values in sorted(monthly.items())
        ]
        breakdown = [
            BreakdownRow(
                id=f"{campaign_key}:{site_code}",
                label=str(values["locatie"]),
                context=(
                    f"{values['campaign_key']} · {values['firma']} · {values['regional']}"
                    f" · {len(values['active_product_codes'])} produse"
                ),
                primary=_money(values["sales"]),
                secondary=values["quantity"],
                tertiary=_money(values["reward"]),
                progress_pct=_ratio(values["qualifying"], values["eligible"]),
                risk=RiskLevel.HEALTHY,
            )
            for (campaign_key, site_code), values in current_by_store.items()
        ]
        top_codes = {
            (str(values["campaign_key"]), str(values["site_code"]))
            for values in sorted(
                current_by_store.values(),
                key=lambda item: Decimal(item["sales"]),
                reverse=True,
            )[:8]
        }
        matrix = [
            MatrixCell(
                x=row_period,
                y=f"{values['campaign_key']} · {values['locatie']}",
                value=_money(values["reward"]),
                risk=RiskLevel.HEALTHY,
            )
            for (row_period, campaign_key, site_code), values in history_by_store.items()
            if (campaign_key, site_code) in top_codes and row_period >= shift_month(period, -5)
        ]
        warnings = sorted({str(item) for row in all_current for item in (row["warnings"] or ())})
        alerts = (
            [
                InsightAlert(
                    id=f"campaign-{metric_name}-partial",
                    severity=AlertSeverity.INFO,
                    title=f"{metric_name.title()} publicat parțial",
                    description="; ".join(warnings),
                )
            ]
            if warnings
            else []
        )
        unavailable_campaigns = {str(row["campaign_key"]) for row in all_current if str(row["status"]) == "unavailable"}
        if unavailable_campaigns and current:
            alerts.append(
                InsightAlert(
                    id=f"campaign-{metric_name}-unavailable-items",
                    severity=AlertSeverity.WARNING,
                    title=f"{metric_name.title()} cu coverage incomplet",
                    description="Campanii neincluse în total: " + ", ".join(sorted(unavailable_campaigns)),
                )
            )
        if not current:
            alerts.append(
                InsightAlert(
                    id=f"campaign-{metric_name}-missing",
                    severity=AlertSeverity.WARNING,
                    title=f"{metric_name.title()} indisponibil",
                    description="Mecanismul nu este publicat în read-model pentru perioada selectată.",
                )
            )
        return ModuleAnalyticsSlice(
            status=source.status if source is not None else SourceStatus.UNAVAILABLE,
            sources={SourceDomain.CAMPAIGNS: source} if source is not None else {},
            axes=(
                ValueAxis(key="primary", label="Vânzări", unit=MetricUnit.CURRENCY),
                ValueAxis(key="secondary", label="Cantitate netă", unit=MetricUnit.INTEGER),
                ValueAxis(key="tertiary", label="Discount" if is_promo else "Recompensă", unit=MetricUnit.CURRENCY),
            ),
            supported_charts=(
                ChartKind.LINE,
                ChartKind.BAR,
                ChartKind.DONUT,
                ChartKind.TREEMAP,
                ChartKind.HEATMAP,
                ChartKind.TABLE,
            ),
            kpis=kpis,
            trend=trend,
            distribution=shares(list(by_campaign.items())),
            breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
            matrix=matrix,
            alerts=alerts,
            entity_dimension="store",
            distribution_dimension="campaign",
        )

    async def _contest_rows(
        self,
        scope: AnalyticsScope,
        *,
        start: str,
        end: str,
    ) -> Sequence[asyncpg.Record]:
        params: list[Any] = [start, end]
        clauses = ["contest.period BETWEEN $1 AND $2"]
        clauses.extend(append_reporting_scope(scope, alias="contest", params=params))
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT contest.period, contest.contest_key, contest.identity_policy,
                       contest.site_code, contest.agent, contest.locatie, contest.firma,
                       contest.regional, contest.asm, contest.focus_units,
                       contest.promo_units, contest.price_units, contest.focus_points,
                       contest.promo_points, contest.price_points, contest.total_points,
                       contest.prize, contest.rank, contest.status, contest.warnings
                FROM reporting_contest_month_v1 AS contest
                WHERE {" AND ".join(clauses)}
                ORDER BY contest.period, contest.contest_key, contest.site_code, contest.agent
                """,
                *params,
            )

    @staticmethod
    def _contest_slice(
        rows: Sequence[asyncpg.Record],
        period: str,
        source: SourceMetadata | None,
    ) -> ModuleAnalyticsSlice:
        if source is None or source.status is SourceStatus.UNAVAILABLE:
            return PostgresInsightRepository._unavailable_slice(
                source=source,
                title="Concurs indisponibil",
                description="Read-model-ul Concurs nu este eligibil în snapshotul selectat.",
            )

        current = [row for row in rows if str(row["period"]) == period and str(row["status"]) != "unavailable"]
        eligible_rows = [row for row in rows if str(row["status"]) != "unavailable"]

        def numeric(row: asyncpg.Record, field: str) -> Decimal:
            value = row[field]
            return Decimal(str(value)) if value is not None else Decimal(0)

        focus_units = sum((numeric(row, "focus_units") for row in current), Decimal(0))
        promo_units = sum((numeric(row, "promo_units") for row in current), Decimal(0))
        price_units = sum((numeric(row, "price_units") for row in current), Decimal(0))
        focus_points = sum((numeric(row, "focus_points") for row in current), Decimal(0))
        promo_points = sum((numeric(row, "promo_points") for row in current), Decimal(0))
        price_points = sum((numeric(row, "price_points") for row in current), Decimal(0))
        points_total = sum((numeric(row, "total_points") for row in current), Decimal(0))
        by_period: dict[str, Decimal] = defaultdict(Decimal)
        by_contest: dict[str, Decimal] = defaultdict(Decimal)
        current_by_agent: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in eligible_rows:
            row_period = str(row["period"])
            by_period[row_period] += numeric(row, "total_points")
            if row_period == period:
                by_contest[str(row["contest_key"])] += numeric(row, "total_points")
                key = (str(row["contest_key"]), str(row["site_code"]), str(row["agent"]))
                bucket = current_by_agent.setdefault(
                    key,
                    {
                        "contest_key": str(row["contest_key"]),
                        "site_code": str(row["site_code"]),
                        "agent": str(row["agent"]),
                        "locatie": str(row["locatie"] or row["site_code"]),
                        "regional": str(row["regional"] or "—"),
                        "focus_units": Decimal(0),
                        "promo_units": Decimal(0),
                        "price_units": Decimal(0),
                        "points_total": Decimal(0),
                        "prize": None,
                        "rank": None,
                    },
                )
                bucket["focus_units"] += numeric(row, "focus_units")
                bucket["promo_units"] += numeric(row, "promo_units")
                bucket["price_units"] += numeric(row, "price_units")
                bucket["points_total"] += numeric(row, "total_points")
                bucket["prize"] = str(row["prize"]) if row["prize"] is not None else bucket["prize"]
                bucket["rank"] = row["rank"] if row["rank"] is not None else bucket["rank"]

        breakdown = [
            BreakdownRow(
                id=f"{values['contest_key']}:{values['site_code']}:{values['agent']}",
                label=values["agent"],
                context=(
                    f"{values['contest_key']} · {values['locatie']} · {values['regional']}"
                    + (f" · premiu {values['prize']}" if values["prize"] else "")
                ),
                primary=values["points_total"],
                secondary=values["focus_units"] + values["promo_units"] + values["price_units"],
                tertiary=Decimal(str(values["rank"])) if values["rank"] is not None else None,
                risk=RiskLevel.HEALTHY,
            )
            for values in current_by_agent.values()
        ]
        warnings = sorted({str(warning) for row in current for warning in (row["warnings"] or ())})
        alerts = (
            [
                InsightAlert(
                    id="contest-partial",
                    severity=AlertSeverity.INFO,
                    title="Concurs publicat parțial",
                    description="; ".join(warnings),
                )
            ]
            if warnings
            else []
        )
        if not current:
            alerts.append(
                InsightAlert(
                    id="contest-missing",
                    severity=AlertSeverity.INFO,
                    title="Concurs nepublicat",
                    description="Nu există rezultate eligibile Concurs pentru scope și perioadă.",
                )
            )
        return ModuleAnalyticsSlice(
            status=source.status,
            sources={SourceDomain.CONTEST: source},
            axes=(
                ValueAxis(key="primary", label="Puncte", unit=MetricUnit.INTEGER),
                ValueAxis(key="secondary", label="Unități", unit=MetricUnit.INTEGER),
                ValueAxis(key="tertiary", label="Loc", unit=MetricUnit.INTEGER),
            ),
            supported_charts=(ChartKind.KPI, ChartKind.LINE, ChartKind.BAR, ChartKind.DONUT, ChartKind.TABLE),
            kpis=[
                KpiMetric(
                    id="campaigns.contest_points_total",
                    label="Puncte totale",
                    value=points_total,
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="campaigns.contest_focus_units",
                    label="Unități Focus",
                    value=focus_units,
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="campaigns.contest_promo_units",
                    label="Unități Promo",
                    value=promo_units,
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="campaigns.contest_price_units",
                    label="Unități Price",
                    value=price_units,
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="campaigns.contest_focus_points",
                    label="Puncte Focus",
                    value=focus_points,
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="campaigns.contest_promo_points",
                    label="Puncte Promo",
                    value=promo_points,
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="campaigns.contest_price_points",
                    label="Puncte Price",
                    value=price_points,
                    unit=MetricUnit.INTEGER,
                ),
            ]
            if current
            else [],
            trend=[TrendPoint(key=item, label=item, primary=value) for item, value in sorted(by_period.items())],
            distribution=shares(list(by_contest.items())),
            breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
            matrix=[],
            alerts=alerts,
            entity_dimension="agent",
            distribution_dimension="contest",
        )

    async def _campaigns(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        meta = await self._meta(
            ModuleId.CAMPAIGNS,
            scope,
            "reporting_campaign_month_v3",
            (SourceDomain.SALES, SourceDomain.CONTEST),
        )
        start = shift_month(scope.period, -11)
        campaign_source = meta.sources.get(SourceDomain.CAMPAIGNS)
        contest_source = meta.sources.get(SourceDomain.CONTEST)
        sales_source = meta.sources.get(SourceDomain.SALES)
        focus_sources = {
            domain: source
            for domain, source in (
                (SourceDomain.CAMPAIGNS, campaign_source),
                (SourceDomain.SALES, sales_source),
            )
            if source is not None
        }
        if (
            campaign_source is None
            or sales_source is None
            or campaign_source.status is SourceStatus.UNAVAILABLE
            or sales_source.status is SourceStatus.UNAVAILABLE
        ):
            focus_status = SourceStatus.UNAVAILABLE
        elif SourceStatus.STALE in {campaign_source.status, sales_source.status}:
            focus_status = SourceStatus.STALE
        elif SourceStatus.PARTIAL in {campaign_source.status, sales_source.status}:
            focus_status = SourceStatus.PARTIAL
        else:
            focus_status = SourceStatus.OFFICIAL
        rows, distribution_rows, mechanism_rows, contest_rows = await asyncio.gather(
            self._campaign_rows(scope, start=start, end=scope.period)
            if focus_status is not SourceStatus.UNAVAILABLE
            else _empty_records(),
            self._campaign_distribution(scope) if focus_status is not SourceStatus.UNAVAILABLE else _empty_records(),
            self._campaign_mechanism_rows(scope, start=start, end=scope.period)
            if campaign_source is not None and campaign_source.status is not SourceStatus.UNAVAILABLE
            else _empty_records(),
            self._contest_rows(scope, start=start, end=scope.period)
            if contest_source is not None and contest_source.status is not SourceStatus.UNAVAILABLE
            else _empty_records(),
        )
        current = [row for row in rows if str(row["import_month"]) == scope.period]
        focus_sales = sum((_money(row["focus_sales"]) for row in current), Decimal(0))
        focus_qty = sum((Decimal(int(row["focus_qty"] or 0)) for row in current), Decimal(0))
        total_qty = sum((Decimal(int(row["total_qty"] or 0)) for row in current), Decimal(0))
        active_products = max((int(row["scope_active_products"] or 0) for row in current), default=0)
        monthly: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"sales": Decimal(0), "focus": Decimal(0), "total": Decimal(0)}
        )
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
            alerts.append(
                InsightAlert(
                    id="campaign-inactive",
                    severity=AlertSeverity.WARNING,
                    title="Magazine fără adopție",
                    description=f"{len(inactive)} magazine nu au rezultat Focus în scope.",
                )
            )
        if not current:
            alerts.append(
                self._missing_alert(
                    ModuleId.CAMPAIGNS,
                    "Nu există date Focus materializate pentru perioada selectată.",
                )
            )
        kpis = (
            [
                KpiMetric(
                    id="campaigns.focus_sales",
                    label="Vânzări Focus",
                    value=_money(focus_sales),
                    unit=MetricUnit.CURRENCY,
                ),
                KpiMetric(
                    id="campaigns.focus_share",
                    label="Pondere Focus",
                    value=_ratio(focus_qty, total_qty) or Decimal(0),
                    unit=MetricUnit.PERCENT,
                ),
                KpiMetric(
                    id="campaigns.active_stores",
                    label="Magazine active",
                    value=Decimal(sum(1 for row in current if _money(row["focus_sales"]) > 0)),
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="campaigns.active_products",
                    label="Produse active",
                    value=Decimal(active_products),
                    unit=MetricUnit.INTEGER,
                ),
            ]
            if current
            else []
        )
        return self._response(
            ModuleId.CAMPAIGNS,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares([(str(row["label"]), _money(row["sales"])) for row in distribution_rows]),
            breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
            matrix=matrix,
            alerts=alerts,
            campaigns={
                "promo": self._commercial_campaign_slice("promo", mechanism_rows, scope.period, source=campaign_source),
                "incentive": self._commercial_campaign_slice(
                    "incentive", mechanism_rows, scope.period, source=campaign_source
                ),
                "folii": self._commercial_campaign_slice(
                    "promo",
                    mechanism_rows,
                    scope.period,
                    source=campaign_source,
                    metric_name="folii",
                    mechanism_variant="same_model_screen_camera",
                ),
                "contest": self._contest_slice(contest_rows, scope.period, contest_source),
            },
            subviews={
                "focus": ModuleAnalyticsSlice(
                    status=focus_status,
                    sources=focus_sources,
                    axes=MODULE_DEFINITIONS[ModuleId.CAMPAIGNS][3],
                    supported_charts=MODULE_DEFINITIONS[ModuleId.CAMPAIGNS][4],
                    kpis=kpis,
                    trend=trend,
                    distribution=shares([(str(row["label"]), _money(row["sales"])) for row in distribution_rows]),
                    breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
                    matrix=matrix,
                    alerts=alerts,
                    entity_dimension="store",
                    distribution_dimension="subcategory",
                )
            },
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
                       ARRAY_AGG(DISTINCT agg.site_code ORDER BY agg.site_code) AS site_codes,
                       COUNT(DISTINCT agg.site_code)::INT AS store_count,
                       MIN(profile.first_seen_month) AS first_seen_month,
                       MAX(profile.active_months_count)::INT AS active_months_count,
                       BOOL_OR(COALESCE(life.is_new, false)) AS is_new,
                       BOOL_OR(COALESCE(life.is_reactivated, false)) AS is_reactivated
                FROM reporting_agent_month agg
                LEFT JOIN reporting_agent_profile profile ON profile.agent = agg.agent
                LEFT JOIN reporting_agent_lifecycle_month life
                  ON life.import_month = agg.import_month AND life.agent = agg.agent
                WHERE {" AND ".join(clauses)}
                GROUP BY agg.import_month, agg.agent
                ORDER BY agg.import_month, agg.agent
                """,
                *params,
            )

    async def _grile_slice(
        self,
        scope: AnalyticsScope,
        source: SourceMetadata | None,
    ) -> ModuleAnalyticsSlice:
        if source is None or source.status is SourceStatus.UNAVAILABLE:
            return self._unavailable_slice(
                source=source,
                title="Grile indisponibil",
                description="Contractul Grile v2 nu are observații eligibile în snapshot.",
            )
        params: list[Any] = [scope.period]
        clauses = ["grile.run_month = $1"]
        clauses.extend(append_reporting_scope(scope, alias="grile", params=params, include_agent=False))
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                f"""
                SELECT grile.period, grile.run_month, grile.source_run_id,
                       grile.site_code, grile.locatie, grile.firma, grile.regional, grile.asm,
                       grile.fill_status, grile.target_status, grile.sales_status,
                       grile.last_error_code, grile.status, grile.warnings
                FROM reporting_grile_month_v2 AS grile
                WHERE {" AND ".join(clauses)}
                ORDER BY grile.site_code
                """,
                *params,
            )
        current = [row for row in rows if str(row["status"]) != "unavailable"]
        problems = [
            row
            for row in current
            if str(row["fill_status"] or "").casefold() != "completat"
            or str(row["target_status"] or "").casefold() != "ok"
            or str(row["sales_status"] or "").casefold() != "ok"
        ]
        errors = [row for row in current if row["last_error_code"] is not None]
        alerts: list[InsightAlert] = []
        if not current:
            alerts.append(
                InsightAlert(
                    id="grile-missing",
                    severity=AlertSeverity.INFO,
                    title="Grile fără observație",
                    description="Nu există observații Grile eligibile pentru scope și perioadă.",
                )
            )
        if problems:
            alerts.append(
                InsightAlert(
                    id="grile-problems",
                    severity=AlertSeverity.WARNING,
                    title="Grile cu neconcordanțe",
                    description=f"{len(problems)} magazine au cel puțin o verificare diferită de OK.",
                )
            )
        if errors:
            alerts.append(
                InsightAlert(
                    id="grile-errors",
                    severity=AlertSeverity.CRITICAL,
                    title="Erori Grile",
                    description=f"{len(errors)} magazine păstrează o ultimă eroare de verificare.",
                )
            )
        warnings = sorted({str(warning) for row in current for warning in (row["warnings"] or ())})
        if warnings:
            alerts.append(
                InsightAlert(
                    id="grile-source-warnings",
                    severity=AlertSeverity.INFO,
                    title="Avertismente sursă Grile",
                    description="; ".join(warnings),
                )
            )
        return ModuleAnalyticsSlice(
            status=source.status,
            sources={SourceDomain.GRILE: source},
            axes=(
                ValueAxis(key="primary", label="Magazine observate", unit=MetricUnit.INTEGER),
                ValueAxis(key="secondary", label="Neconcordanțe", unit=MetricUnit.INTEGER),
            ),
            supported_charts=(ChartKind.KPI, ChartKind.BAR, ChartKind.TABLE),
            kpis=[
                KpiMetric(
                    id="grile.observed_stores",
                    label="Magazine observate",
                    value=Decimal(len(current)),
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="grile.problem_stores",
                    label="Magazine cu neconcordanțe",
                    value=Decimal(len(problems)),
                    unit=MetricUnit.INTEGER,
                    risk=RiskLevel.WATCH if problems else RiskLevel.HEALTHY,
                ),
            ]
            if current
            else [],
            trend=[],
            distribution=[],
            breakdown=[
                BreakdownRow(
                    id=str(row["site_code"]),
                    label=str(row["locatie"] or row["site_code"]),
                    context=f"{row['firma'] or '—'} · {row['regional'] or '—'} · run {row['source_run_id']}",
                    primary=Decimal(1),
                    secondary=Decimal(
                        (str(row["fill_status"] or "").casefold() != "completat")
                        + (str(row["target_status"] or "").casefold() != "ok")
                        + (str(row["sales_status"] or "").casefold() != "ok")
                    ),
                    tertiary=Decimal(1) if row["last_error_code"] is not None else Decimal(0),
                    risk=RiskLevel.RISK
                    if row["last_error_code"] is not None
                    else RiskLevel.WATCH
                    if row in problems
                    else RiskLevel.HEALTHY,
                )
                for row in current
            ],
            matrix=[],
            alerts=alerts,
            entity_dimension="store",
        )

    async def _workforce(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        meta = await self._meta(
            ModuleId.WORKFORCE,
            scope,
            "reporting_agent_month/reporting_agent_profile/reporting_grile_month_v2",
            (SourceDomain.VISITS, SourceDomain.GRILE),
        )
        workforce_source = meta.sources.get(SourceDomain.WORKFORCE)
        visits_source = meta.sources.get(SourceDomain.VISITS)
        grile_source = meta.sources.get(SourceDomain.GRILE)
        rows, grile, visits = await asyncio.gather(
            self._workforce_rows(scope)
            if workforce_source is not None and workforce_source.status is not SourceStatus.UNAVAILABLE
            else _empty_records(),
            self._grile_slice(scope, grile_source),
            self._visit_slice(scope, visits_source),
        )
        current = [row for row in rows if str(row["import_month"]) == scope.period]
        headcount = len(current)
        total_sales = sum((_money(row["total_sales"]) for row in current), Decimal(0))
        staffed_stores = {str(site_code) for row in current for site_code in (row["site_codes"] or ())}
        selected_store_count = len(scope.stores)
        if (
            selected_store_count == 0
            and not any((scope.firm, scope.regional, scope.asm, scope.agent))
            and workforce_source is not None
        ):
            selected_store_count = int(workforce_source.coverage_denominator or 0)
        new_count = sum(1 for row in current if row["is_new"])
        reactivated_count = sum(1 for row in current if row["is_reactivated"])
        movement_count = new_count + reactivated_count
        stability = (
            _percent(Decimal(max(headcount - movement_count, 0)) * Decimal("100") / Decimal(headcount))
            if headcount
            else None
        )
        coverage = (
            _percent(Decimal(len(staffed_stores)) * Decimal("100") / Decimal(selected_store_count))
            if selected_store_count
            else None
        )
        monthly: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {"headcount": Decimal(0), "sales": Decimal(0), "new": Decimal(0)}
        )
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
            if f"{row['site_code']}:{row['agent']}" in top_agents
            and str(row["import_month"]) >= shift_month(scope.period, -5)
        ]
        alerts = list(grile.alerts)
        alerts.insert(
            0,
            InsightAlert(
                id="workforce-observed-commercial-activity",
                severity=AlertSeverity.INFO,
                title="Activitate comercială observată",
                description=(
                    "People, Stability, Coverage și Movements provin din activitate comercială observată; "
                    "nu sunt registru oficial de personal. Movements include numai nou/reactivat; "
                    "plecările și transferurile nu sunt publicate."
                ),
            ),
        )
        if not current:
            alerts.insert(
                0,
                self._missing_alert(ModuleId.WORKFORCE, "Nu există agenți activi în scope-ul selectat."),
            )
        kpis = (
            [
                KpiMetric(
                    id="workforce.headcount",
                    label="Persoane active observate",
                    value=Decimal(headcount),
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="workforce.productivity",
                    label="Productivitate / agent",
                    value=_money(total_sales / Decimal(headcount)) if headcount else Decimal(0),
                    unit=MetricUnit.CURRENCY,
                ),
                KpiMetric(
                    id="workforce.stability",
                    label="Stabilitate activitate observată",
                    value=stability or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=_risk(stability),
                ),
                KpiMetric(
                    id="workforce.new_agents",
                    label="Nou observați",
                    value=Decimal(new_count),
                    unit=MetricUnit.INTEGER,
                ),
                KpiMetric(
                    id="workforce.reactivated_agents",
                    label="Reactivați observați",
                    value=Decimal(reactivated_count),
                    unit=MetricUnit.INTEGER,
                ),
            ]
            if current
            else []
        )
        if current and coverage is not None:
            kpis.append(
                KpiMetric(
                    id="workforce.coverage",
                    label="Acoperire magazine selectate observată",
                    value=coverage,
                    unit=MetricUnit.PERCENT,
                    risk=_risk(coverage),
                )
            )
        workforce_sources = {SourceDomain.WORKFORCE: workforce_source} if workforce_source is not None else {}
        # Commercial activity is useful but never a substitute for an official roster.
        workforce_status = (
            SourceStatus.PARTIAL
            if workforce_source is not None and workforce_source.status is not SourceStatus.UNAVAILABLE
            else SourceStatus.UNAVAILABLE
        )
        return self._response(
            ModuleId.WORKFORCE,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares(list(tenure_bands.items())),
            breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
            matrix=matrix,
            alerts=alerts,
            visits=visits,
            subviews={
                "people": ModuleAnalyticsSlice(
                    status=workforce_status,
                    sources=workforce_sources,
                    axes=(ValueAxis(key="primary", label="Persoane active observate", unit=MetricUnit.INTEGER),),
                    supported_charts=(ChartKind.KPI, ChartKind.LINE, ChartKind.TABLE),
                    kpis=[item for item in kpis if item.id == "workforce.headcount"],
                    trend=trend,
                    distribution=shares(list(tenure_bands.items())),
                    breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
                    matrix=[],
                    alerts=alerts[:1],
                    entity_dimension="agent",
                    distribution_dimension="tenure",
                ),
                "stability": ModuleAnalyticsSlice(
                    status=workforce_status,
                    sources=workforce_sources,
                    axes=(ValueAxis(key="primary", label="Stabilitate activitate observată", unit=MetricUnit.PERCENT),),
                    supported_charts=(ChartKind.KPI, ChartKind.LINE, ChartKind.TABLE),
                    kpis=[item for item in kpis if item.id == "workforce.stability"],
                    trend=trend,
                    distribution=[],
                    breakdown=[],
                    matrix=[],
                    alerts=alerts[:1],
                ),
                "coverage": ModuleAnalyticsSlice(
                    status=workforce_status,
                    sources=workforce_sources,
                    axes=(
                        ValueAxis(
                            key="primary", label="Acoperire magazine selectate observată", unit=MetricUnit.PERCENT
                        ),
                    ),
                    supported_charts=(ChartKind.KPI, ChartKind.TABLE),
                    kpis=[item for item in kpis if item.id == "workforce.coverage"],
                    trend=[],
                    distribution=[],
                    breakdown=[],
                    matrix=[],
                    alerts=alerts[:1],
                ),
                "movements": ModuleAnalyticsSlice(
                    status=workforce_status,
                    sources=workforce_sources,
                    axes=(ValueAxis(key="primary", label="Mișcări observate", unit=MetricUnit.INTEGER),),
                    supported_charts=(ChartKind.KPI, ChartKind.TABLE),
                    kpis=[item for item in kpis if item.id in {"workforce.new_agents", "workforce.reactivated_agents"}],
                    trend=[],
                    distribution=[],
                    breakdown=[item for item in breakdown if item.risk is RiskLevel.WATCH],
                    matrix=[],
                    alerts=alerts[:1],
                    entity_dimension="agent",
                ),
                "grile": grile,
            },
        )

    async def _compensation_rows(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        start = shift_month(scope.period, -11)
        params: list[Any] = [start, scope.period]
        firm_filter = ""
        if scope.firm:
            params.append(scope.firm)
            firm_filter = f"AND LOWER(compensation.company_name) = LOWER(${len(params)})"
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT compensation.period, compensation.company_name,
                       compensation.eligible_person_count,
                       compensation.payroll_total,
                       compensation.average_salary_eligible,
                       compensation.median_salary
                FROM reporting_compensation_month_v1 compensation
                WHERE compensation.period BETWEEN $1 AND $2
                  {firm_filter}
                ORDER BY compensation.period, compensation.company_name
                """,
                *params,
            )

    async def _compensation(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        compensation_rows, sales_rows, meta = await asyncio.gather(
            self._compensation_rows(scope),
            self._sales_history(scope, start=shift_month(scope.period, -11), end=scope.period),
            self._meta(
                ModuleId.COMPENSATION,
                scope,
                "reporting_compensation_month_v1",
                (SourceDomain.SALES,),
            ),
        )
        visible_compensation_rows = filter_visible_compensation_rows(compensation_rows)
        selected_company = scope.firm or "__ALL__"
        current = [
            row
            for row in visible_compensation_rows
            if str(row["period"]) == scope.period and str(row["company_name"]).casefold() == selected_company.casefold()
        ]
        current_row = current[0] if current else None
        payroll = _money(current_row["payroll_total"]) if current_row else Decimal(0)
        average = _money(current_row["average_salary_eligible"]) if current_row else Decimal(0)
        median = _money(current_row["median_salary"]) if current_row else Decimal(0)
        sales = sum(
            (_money(row["total_sales"]) for row in sales_rows if str(row["import_month"]) == scope.period),
            Decimal(0),
        )
        ratio = _ratio(payroll, sales)
        selected_rows = [
            row
            for row in visible_compensation_rows
            if str(row["company_name"]).casefold() == selected_company.casefold()
        ]
        trend = [
            TrendPoint(
                key=str(row["period"]),
                label=str(row["period"]),
                primary=_money(row["payroll_total"]),
                secondary=_money(row["average_salary_eligible"]),
                comparison=_money(row["median_salary"]),
            )
            for row in selected_rows
        ]
        company_rows = [
            row
            for row in visible_compensation_rows
            if str(row["period"]) == scope.period and str(row["company_name"]) != "__ALL__"
        ]
        breakdown = [
            BreakdownRow(
                id=str(row["company_name"]),
                label=str(row["company_name"]),
                context=f"{int(row['eligible_person_count'])} persoane eligibile",
                primary=_money(row["payroll_total"]),
                secondary=_money(row["average_salary_eligible"]),
                tertiary=_money(row["median_salary"]),
                risk=RiskLevel.HEALTHY,
            )
            for row in company_rows
        ]
        matrix = [
            MatrixCell(
                x=str(row["period"]),
                y=str(row["company_name"]),
                value=_money(row["payroll_total"]),
                risk=RiskLevel.HEALTHY,
            )
            for row in visible_compensation_rows
            if str(row["company_name"]) != "__ALL__" and str(row["period"]) >= shift_month(scope.period, -5)
        ]
        alerts: list[InsightAlert] = []
        if not current:
            alerts.append(
                InsightAlert(
                    id="compensation-suppressed-or-missing",
                    severity=AlertSeverity.WARNING,
                    title="Date agregate indisponibile",
                    description="Luna nu are un batch aprobat sau pragul fail-closed de minimum trei persoane nu este îndeplinit.",
                )
            )
        kpis = (
            [
                KpiMetric(
                    id="compensation.payroll",
                    label="Cost salarial",
                    value=_money(payroll),
                    unit=MetricUnit.CURRENCY,
                ),
                KpiMetric(
                    id="compensation.average",
                    label="Salariu mediu",
                    value=average,
                    unit=MetricUnit.CURRENCY,
                ),
                KpiMetric(
                    id="compensation.median",
                    label="Salariu median",
                    value=median,
                    unit=MetricUnit.CURRENCY,
                ),
                KpiMetric(
                    id="compensation.sales_ratio",
                    label="Cost / vânzări",
                    value=ratio or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=RiskLevel.WATCH if ratio and ratio > Decimal("25") else RiskLevel.HEALTHY,
                ),
            ]
            if current
            else []
        )
        return self._response(
            ModuleId.COMPENSATION,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares([(row.label, row.primary) for row in breakdown]),
            breakdown=sorted(breakdown, key=lambda item: item.primary, reverse=True),
            matrix=matrix,
            alerts=alerts,
        )

    async def _finance_rows(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        start = shift_month(scope.period, -11)
        params: list[Any] = [start, scope.period]
        filters: list[str] = []
        if scope.stores:
            params.append(list(scope.stores))
            filters.append(f"row.site_code = ANY(${len(params)}::text[])")
        else:
            if scope.firm:
                params.append(scope.firm)
                filters.append(
                    f"(LOWER(row.firma) = LOWER(${len(params)}) "
                    f"OR (row.is_unallocated AND LOWER(row.company_name) = LOWER(${len(params)})))"
                )
            if scope.regional:
                params.append(list(scope.regional))
                filters.append(f"row.regional = ANY(${len(params)}::text[])")
            if scope.asm:
                params.append(scope.asm)
                filters.append(f"row.asm = ${len(params)}")
        filter_sql = " AND ".join(filters) if filters else "TRUE"
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT row.period, row.company_name, row.source_site_code,
                       row.source_location_name, row.site_code AS canonical_site_code,
                       row.category_code, row.amount, row.data_kind,
                       COALESCE(row.regional, 'Nealocat') AS regional,
                       COALESCE(row.asm, 'Nealocat') AS asm,
                       row.is_unallocated
                FROM reporting_finance_month_v1 row
                WHERE row.period BETWEEN $1 AND $2
                  AND {filter_sql}
                ORDER BY row.period, row.company_name, row.site_code, row.category_code
                """,
                *params,
            )

    async def _finance(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        rows, meta = await asyncio.gather(
            self._finance_rows(scope),
            self._meta(ModuleId.FINANCE, scope, "reporting_finance_month_v1"),
        )
        monthly_amounts: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        monthly_estimate: dict[str, bool] = defaultdict(bool)
        store_amounts: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        store_labels: dict[tuple[str, str], tuple[str, str]] = {}
        category_current: dict[str, Decimal] = defaultdict(Decimal)
        for row in rows:
            period = str(row["period"])
            category = str(row["category_code"])
            amount = _money(row["amount"])
            monthly_amounts[period][category] += amount
            monthly_estimate[period] |= str(row["data_kind"]) == "estimated"
            if period == scope.period:
                category_current[category] += amount
            if row["is_unallocated"]:
                continue
            key = (str(row["company_name"]), str(row["canonical_site_code"]))
            store_amounts[key][category] += amount
            store_labels[key] = (str(row["source_location_name"]), str(row["regional"]))
        current_metrics = finance_metrics(monthly_amounts.get(scope.period, {}))
        margin = _ratio(current_metrics["ebit"], current_metrics["revenue"])
        trend = []
        for period, amounts in sorted(monthly_amounts.items()):
            values = finance_metrics(amounts)
            trend.append(
                TrendPoint(
                    key=period,
                    label=period,
                    primary=values["revenue"],
                    secondary=values["ebit"],
                    target=_ratio(values["ebit"], values["revenue"]),
                    is_estimate=monthly_estimate[period],
                )
            )
        breakdown: list[BreakdownRow] = []
        for key, amounts in store_amounts.items():
            values = finance_metrics(amounts)
            label, regional = store_labels[key]
            store_margin = _ratio(values["ebit"], values["revenue"])
            breakdown.append(
                BreakdownRow(
                    id=f"{key[0]}:{key[1]}",
                    label=label,
                    context=f"{key[0]} · {regional}",
                    primary=values["revenue"],
                    secondary=values["ebit"],
                    tertiary=values["operating_costs"],
                    progress_pct=store_margin,
                    risk=RiskLevel.RISK if values["ebit"] < 0 else RiskLevel.HEALTHY,
                )
            )
        top_stores = {item.id for item in sorted(breakdown, key=lambda item: item.primary, reverse=True)[:8]}
        matrix: list[MatrixCell] = []
        by_store_month: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for row in rows:
            if row["is_unallocated"]:
                continue
            period = str(row["period"])
            identifier = f"{row['company_name']}:{row['canonical_site_code']}"
            if identifier in top_stores and period >= shift_month(scope.period, -5):
                by_store_month[(identifier, period)][str(row["category_code"])] += _money(row["amount"])
        label_by_id = {item.id: item.label for item in breakdown}
        for (identifier, period), amounts in by_store_month.items():
            values = finance_metrics(amounts)
            store_margin = _ratio(values["ebit"], values["revenue"])
            matrix.append(
                MatrixCell(
                    x=period,
                    y=label_by_id[identifier],
                    value=store_margin or Decimal(0),
                    risk=RiskLevel.RISK if values["ebit"] < 0 else RiskLevel.HEALTHY,
                )
            )
        cost_items = [
            (CATEGORY_LABELS.get(code, code), amount)
            for code, amount in category_current.items()
            if code in COGS_CODES | OPERATING_CODES | {"a1"}
        ]
        alerts: list[InsightAlert] = []
        negative = [item for item in breakdown if item.secondary is not None and item.secondary < 0]
        if negative:
            alerts.append(
                InsightAlert(
                    id="finance-negative",
                    severity=AlertSeverity.CRITICAL,
                    title="Magazine cu EBIT negativ",
                    description=f"{len(negative)} magazine au EBIT negativ în intervalul analizat.",
                )
            )
        if monthly_estimate.get(scope.period):
            alerts.append(
                InsightAlert(
                    id="finance-estimate",
                    severity=AlertSeverity.WARNING,
                    title="Perioadă estimată",
                    description="Cel puțin o componentă P&L este estimată; actualele au prioritate unde există.",
                )
            )
        if not rows:
            alerts.append(self._missing_alert(ModuleId.FINANCE, "Nu există date P&L pentru scope-ul selectat."))
        kpis = (
            [
                KpiMetric(
                    id="finance.revenue",
                    label="Venit net",
                    value=current_metrics["revenue"],
                    unit=MetricUnit.CURRENCY,
                ),
                KpiMetric(
                    id="finance.ebit",
                    label="EBIT",
                    value=current_metrics["ebit"],
                    unit=MetricUnit.CURRENCY,
                    risk=RiskLevel.RISK if current_metrics["ebit"] < 0 else RiskLevel.HEALTHY,
                ),
                KpiMetric(
                    id="finance.ebit_margin",
                    label="Marjă EBIT",
                    value=margin or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=RiskLevel.RISK if current_metrics["ebit"] < 0 else RiskLevel.HEALTHY,
                ),
                KpiMetric(
                    id="finance.operating_costs",
                    label="Cost operațional",
                    value=current_metrics["operating_costs"],
                    unit=MetricUnit.CURRENCY,
                ),
            ]
            if rows
            else []
        )
        return self._response(
            ModuleId.FINANCE,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares(cost_items),
            breakdown=sorted(breakdown, key=lambda item: item.secondary or Decimal(0)),
            matrix=matrix,
            alerts=alerts,
        )

    async def _planning_rows(self, scope: AnalyticsScope) -> Sequence[asyncpg.Record]:
        params: list[Any] = [shift_month(scope.period, -11), scope.period]
        store_clauses = append_reporting_scope(scope, alias="scenario", params=params, include_agent=False)
        scope_sql = " AND ".join(store_clauses) if store_clauses else "TRUE"
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH forecast AS (
                    SELECT scenario.*
                    FROM reporting_planning_scenario_v2 AS scenario
                    WHERE scenario.period BETWEEN $1 AND $2
                      AND scenario.authority_kind = 'forecast'
                      AND scenario.metric = 'sales_value'
                      AND scenario.status <> 'unavailable'
                      AND {scope_sql}
                ), target AS (
                    SELECT scenario.period,
                           scenario.site_code,
                           SUM(scenario.target_value) AS target_value,
                           MIN(scenario.status) AS target_status
                    FROM reporting_planning_scenario_v2 AS scenario
                    WHERE scenario.period BETWEEN $1 AND $2
                      AND scenario.authority_kind = 'target'
                      AND scenario.status <> 'unavailable'
                    GROUP BY scenario.period, scenario.site_code
                ), planning AS (
                    SELECT forecast.period AS forecast_month,
                           forecast.site_code,
                           forecast.locatie,
                           forecast.firma,
                           forecast.regional,
                           forecast.asm,
                           forecast.forecast_value AS forecast_sales,
                           target.target_value,
                           forecast.status AS forecast_status,
                           target.target_status
                    FROM forecast
                    LEFT JOIN target
                      ON target.period = forecast.period
                     AND target.site_code = forecast.site_code
                ), actual AS (
                    SELECT agg.import_month, agg.site_code, SUM(agg.total_sales) AS actual_sales
                    FROM reporting_agent_month agg
                    WHERE agg.import_month BETWEEN $1 AND $2
                    GROUP BY agg.import_month, agg.site_code
                )
                SELECT planning.*, actual.actual_sales
                FROM planning
                LEFT JOIN actual
                  ON actual.import_month = planning.forecast_month
                 AND actual.site_code = planning.site_code
                ORDER BY planning.forecast_month, planning.forecast_sales DESC
                """,
                *params,
            )

    async def _planning(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        rows, meta = await asyncio.gather(
            self._planning_rows(scope),
            self._meta(
                ModuleId.PLANNING,
                scope,
                "reporting_planning_scenario_v2",
                (SourceDomain.SALES,),
            ),
        )
        current = [row for row in rows if str(row["forecast_month"]) == scope.period]
        forecast = sum((_money(row["forecast_sales"]) for row in current), Decimal(0))
        has_target = any(row["target_value"] is not None for row in current)
        target = sum(
            (_money(row["target_value"]) for row in current if row["target_value"] is not None),
            Decimal(0),
        )
        has_actual = any(row["actual_sales"] is not None for row in current)
        actual = sum(
            (_money(row["actual_sales"]) for row in current if row["actual_sales"] is not None),
            Decimal(0),
        )
        monthly: dict[str, dict[str, Decimal | bool]] = defaultdict(
            lambda: {
                "forecast": Decimal(0),
                "actual": Decimal(0),
                "target": Decimal(0),
                "has_actual": False,
                "has_target": False,
            }
        )
        for row in rows:
            item = monthly[str(row["forecast_month"])]
            item["forecast"] = Decimal(item["forecast"]) + _money(row["forecast_sales"])
            if row["target_value"] is not None:
                item["target"] = Decimal(item["target"]) + _money(row["target_value"])
                item["has_target"] = True
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
            trend.append(
                TrendPoint(
                    key=period,
                    label=period,
                    primary=forecast_value,
                    comparison=actual_value,
                    target=_money(values["target"]) if bool(values.get("has_target")) else None,
                    is_estimate=actual_value is None,
                )
            )
        accuracy = _percent(sum(accuracies, Decimal(0)) / Decimal(len(accuracies))) if accuracies else None
        breakdown: list[BreakdownRow] = []
        for row in current:
            forecast_value = _money(row["forecast_sales"])
            target_value = _money(row["target_value"]) if row["target_value"] is not None else None
            actual_value = _money(row["actual_sales"]) if row["actual_sales"] is not None else None
            progress = _ratio(forecast_value, target_value) if target_value is not None else None
            breakdown.append(
                BreakdownRow(
                    id=str(row["site_code"]),
                    label=str(row["locatie"]),
                    context=f"{row['firma']} · {row['regional']}",
                    primary=forecast_value,
                    secondary=actual_value,
                    tertiary=target_value,
                    progress_pct=progress,
                    delta_pct=_delta(forecast_value, actual_value) if actual_value is not None else None,
                    risk=_risk(progress),
                )
            )
        distribution_by_regional: dict[str, Decimal] = defaultdict(Decimal)
        for row in current:
            distribution_by_regional[str(row["regional"])] += _money(row["forecast_sales"])
        top_codes = {item.id for item in sorted(breakdown, key=lambda item: item.primary, reverse=True)[:8]}
        matrix = [
            MatrixCell(
                x=str(row["forecast_month"]),
                y=str(row["locatie"]),
                value=_ratio(_money(row["forecast_sales"]), _money(row["actual_sales"])) or Decimal(0),
                risk=RiskLevel.HEALTHY,
            )
            for row in rows
            if str(row["site_code"]) in top_codes
            and str(row["forecast_month"]) >= shift_month(scope.period, -5)
            and row["actual_sales"] is not None
        ]
        alerts: list[InsightAlert] = []
        if not current:
            alerts.append(
                self._missing_alert(
                    ModuleId.PLANNING,
                    "Nu există un forecast complet pentru perioada și scope-ul selectat.",
                )
            )
        elif target > 0 and forecast < target:
            alerts.append(
                InsightAlert(
                    id="planning-gap",
                    severity=AlertSeverity.WARNING,
                    title="Forecast sub target",
                    description=f"Gap-ul proiectat este {_money(forecast - target)} RON.",
                )
            )
        kpis: list[KpiMetric] = []
        if current:
            kpis.append(
                KpiMetric(
                    id="planning.forecast",
                    label="Forecast",
                    value=_money(forecast),
                    unit=MetricUnit.CURRENCY,
                    supporting_value=_money(target) if has_target else None,
                    supporting_label="Target" if has_target else None,
                    risk=_risk(_ratio(forecast, target)) if has_target else RiskLevel.HEALTHY,
                )
            )
            if has_target:
                kpis.append(
                    KpiMetric(
                        id="planning.target_gap",
                        label="Gap față de target",
                        value=_money(forecast - target),
                        unit=MetricUnit.CURRENCY,
                        risk=_risk(_ratio(forecast, target)),
                    )
                )
            if accuracy is not None:
                kpis.append(
                    KpiMetric(
                        id="planning.accuracy",
                        label="Acuratețe istorică",
                        value=accuracy,
                        unit=MetricUnit.PERCENT,
                        risk=_risk(accuracy),
                    )
                )
            if has_actual:
                kpis.append(
                    KpiMetric(
                        id="planning.actual",
                        label="Actual disponibil",
                        value=_money(actual),
                        unit=MetricUnit.CURRENCY,
                    )
                )
        return self._response(
            ModuleId.PLANNING,
            meta,
            kpis=kpis,
            trend=trend,
            distribution=shares(list(distribution_by_regional.items())),
            breakdown=sorted(breakdown, key=lambda item: item.progress_pct or Decimal(0)),
            matrix=matrix,
            alerts=alerts,
            subviews={
                "forecast": ModuleAnalyticsSlice(
                    status=(
                        meta.sources[SourceDomain.PLANNING].status
                        if SourceDomain.PLANNING in meta.sources
                        else SourceStatus.UNAVAILABLE
                    ),
                    sources=(
                        {SourceDomain.PLANNING: meta.sources[SourceDomain.PLANNING]}
                        if SourceDomain.PLANNING in meta.sources
                        else {}
                    ),
                    axes=MODULE_DEFINITIONS[ModuleId.PLANNING][3],
                    supported_charts=MODULE_DEFINITIONS[ModuleId.PLANNING][4],
                    kpis=kpis,
                    trend=trend,
                    distribution=shares(list(distribution_by_regional.items())),
                    breakdown=sorted(breakdown, key=lambda item: item.progress_pct or Decimal(0)),
                    matrix=matrix,
                    alerts=alerts,
                    entity_dimension="store",
                    distribution_dimension="regional",
                )
            },
        )

    @staticmethod
    def _performance_alerts(rows: Sequence[BreakdownRow]) -> list[InsightAlert]:
        alerts: list[InsightAlert] = []
        for row in rows:
            if row.risk is RiskLevel.RISK:
                alerts.append(
                    InsightAlert(
                        id=f"risk-{row.id}",
                        severity=AlertSeverity.WARNING,
                        title="Entitate sub ritmul necesar",
                        description=f"Realizarea curentă este {row.progress_pct}%.",
                        entity_label=row.label,
                    )
                )
            if len(alerts) >= 5:
                break
        if not alerts and rows:
            alerts.append(
                InsightAlert(
                    id="scope-healthy",
                    severity=AlertSeverity.INFO,
                    title="Fără abateri majore",
                    description="Nicio entitate nu a intrat în pragul critic curent.",
                )
            )
        return alerts

    @staticmethod
    def _missing_alert(module: ModuleId, description: str) -> InsightAlert:
        return InsightAlert(
            id=f"{module.value}-missing",
            severity=AlertSeverity.CRITICAL,
            title="Date indisponibile",
            description=description,
        )
