from __future__ import annotations

import calendar
import hashlib
import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

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
    SourceDomain,
    TrendPoint,
    ValueAxis,
)
from unihub_insight_api.repositories.demo import (
    DEMO_AGENTS,
    DemoAnalyticsRepository,
)
from unihub_insight_api.services import scope_label

BUCHAREST = ZoneInfo("Europe/Bucharest")
QUANT = Decimal("0.01")


@dataclass(frozen=True)
class ModuleProfile:
    title: str
    description: str
    capability: Capability
    axes: tuple[ValueAxis, ValueAxis, ValueAxis]
    charts: tuple[ChartKind, ...]
    categories: tuple[str, ...]
    base: Decimal


def _axis(key: str, label: str, unit: MetricUnit) -> ValueAxis:
    return ValueAxis(key=key, label=label, unit=unit)


PROFILES: dict[ModuleId, ModuleProfile] = {
    ModuleId.SALES: ModuleProfile(
        title="Sales Intelligence",
        description="Pace, trend, tranzacții și contribuția comercială.",
        capability=Capability.ANALYTICS,
        axes=(
            _axis("primary", "Vânzări", MetricUnit.CURRENCY),
            _axis("secondary", "Cantitate", MetricUnit.INTEGER),
            _axis("tertiary", "Bonuri", MetricUnit.INTEGER),
        ),
        charts=(ChartKind.LINE, ChartKind.AREA, ChartKind.BAR, ChartKind.DONUT, ChartKind.TREEMAP, ChartKind.TABLE),
        categories=("MOBIUP", "MOBICELL", "Online asistat", "Alte canale"),
        base=Decimal("930000"),
    ),
    ModuleId.PERFORMANCE: ModuleProfile(
        title="Performance",
        description="Comparație, stabilitate și prioritizare pe structură comercială.",
        capability=Capability.ANALYTICS,
        axes=(
            _axis("primary", "Realizare target", MetricUnit.PERCENT),
            _axis("secondary", "Vânzări", MetricUnit.CURRENCY),
            _axis("tertiary", "Volatilitate", MetricUnit.PERCENT),
        ),
        charts=(
            ChartKind.BAR,
            ChartKind.HEATMAP,
            ChartKind.SCATTER,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        ),
        categories=("La target", "Aproape de target", "Sub ritm", "Fără target"),
        base=Decimal("96"),
    ),
    ModuleId.CAMPAIGNS: ModuleProfile(
        title="Campaigns",
        description="Focus, Promo, Incentive, Concurs și acoperire comercială.",
        capability=Capability.ANALYTICS,
        axes=(
            _axis("primary", "Vânzări Focus", MetricUnit.CURRENCY),
            _axis("secondary", "Cantitate", MetricUnit.INTEGER),
            _axis("tertiary", "Pondere Focus", MetricUnit.PERCENT),
        ),
        charts=(ChartKind.LINE, ChartKind.BAR, ChartKind.DONUT, ChartKind.TREEMAP, ChartKind.HEATMAP, ChartKind.TABLE),
        categories=("Focus", "Promo", "Incentive", "Concurs", "Folii premium"),
        base=Decimal("185000"),
    ),
    ModuleId.WORKFORCE: ModuleProfile(
        title="Workforce",
        description="Headcount, acoperire, stabilitate și productivitate.",
        capability=Capability.MANAGEMENT,
        axes=(
            _axis("primary", "Headcount activ", MetricUnit.INTEGER),
            _axis("secondary", "Productivitate / agent", MetricUnit.CURRENCY),
            _axis("tertiary", "Acoperire", MetricUnit.PERCENT),
        ),
        charts=(
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.TREEMAP,
            ChartKind.HEATMAP,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        ),
        categories=("< 3 luni", "3–12 luni", "1–3 ani", "3+ ani"),
        base=Decimal("38"),
    ),
    ModuleId.COMPENSATION: ModuleProfile(
        title="Compensation",
        description="Cost salarial, distribuție și relația cu performanța.",
        capability=Capability.HR,
        axes=(
            _axis("primary", "Cost salarial", MetricUnit.CURRENCY),
            _axis("secondary", "Salariu mediu", MetricUnit.CURRENCY),
            _axis("tertiary", "Cost / vânzări", MetricUnit.PERCENT),
        ),
        charts=(
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.SCATTER,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        ),
        categories=("Fix", "Variabil", "Bonuri", "Alte componente"),
        base=Decimal("365000"),
    ),
    ModuleId.FINANCE: ModuleProfile(
        title="Finance & P&L",
        description="Venit, cost, profit, marjă și reconciliere.",
        capability=Capability.PNL,
        axes=(
            _axis("primary", "Venit net", MetricUnit.CURRENCY),
            _axis("secondary", "EBIT", MetricUnit.CURRENCY),
            _axis("tertiary", "Marjă EBIT", MetricUnit.PERCENT),
        ),
        charts=(
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.WATERFALL,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.TABLE,
        ),
        categories=("Marfă", "Salarii", "Chirii", "Servicii", "Amortizare"),
        base=Decimal("780000"),
    ),
    ModuleId.PLANNING: ModuleProfile(
        title="Planning",
        description="Forecast, target, acuratețe și scenarii versionabile.",
        capability=Capability.MANAGEMENT,
        axes=(
            _axis("primary", "Forecast", MetricUnit.CURRENCY),
            _axis("secondary", "Actual / target", MetricUnit.CURRENCY),
            _axis("tertiary", "Acuratețe", MetricUnit.PERCENT),
        ),
        charts=(ChartKind.LINE, ChartKind.AREA, ChartKind.BAR, ChartKind.SCATTER, ChartKind.TABLE),
        categories=("Downside", "Base", "Upside", "Target"),
        base=Decimal("970000"),
    ),
}


PRODUCTS = (
    "Folie premium",
    "Căști wireless",
    "Încărcător rapid",
    "Husă premium",
    "Baterie externă",
    "Suport auto",
    "Cablu date",
    "Protecție cameră",
    "Adaptor rețea",
    "Pachet travel",
    "Boxă portabilă",
    "Smart tag",
)


def _number(value: Decimal | float | int | str) -> Decimal:
    return (value if isinstance(value, Decimal) else Decimal(str(value))).quantize(
        QUANT,
        rounding=ROUND_HALF_UP,
    )


def _seed(module: ModuleId, scope: AnalyticsScope, suffix: str = "") -> int:
    payload = f"{module.value}|{scope.model_dump_json()}|{suffix}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _shift_month(period: str, offset: int) -> str:
    year, month = (int(part) for part in period.split("-"))
    absolute = year * 12 + month - 1 + offset
    next_year, zero_month = divmod(absolute, 12)
    return f"{next_year:04d}-{zero_month + 1:02d}"


def _risk(progress: Decimal | None) -> RiskLevel:
    if progress is None or progress < Decimal("82"):
        return RiskLevel.RISK
    if progress < Decimal("96"):
        return RiskLevel.WATCH
    return RiskLevel.HEALTHY


def _delta(current: Decimal, previous: Decimal) -> Decimal | None:
    if previous == 0:
        return None
    return _number((current - previous) * Decimal("100") / previous)


def _meta(module: ModuleId, scope: AnalyticsScope) -> OverviewMeta:
    now = datetime.now(BUCHAREST)
    current_period = f"{now.year:04d}-{now.month:02d}"
    year, month = (int(part) for part in scope.period.split("-"))
    days = calendar.monthrange(year, month)[1]
    if scope.period < current_period:
        as_of = date(year, month, days)
        is_final = True
    elif scope.period == current_period:
        as_of = date(year, month, min(now.day, days))
        is_final = False
    else:
        as_of = None
        is_final = False
    return OverviewMeta(
        period=scope.period,
        comparison=scope.comparison,
        as_of=as_of,
        is_final=is_final,
        data_mode=DataMode.DEMO,
        scope_label=scope_label(scope),
        generated_at=datetime.now(UTC),
        source=f"deterministic-demo:{module.value}",
    )


def _entities(module: ModuleId, scope: AnalyticsScope) -> list[tuple[str, str, str]]:
    stores = DemoAnalyticsRepository._selected_stores(scope)
    if module is ModuleId.CAMPAIGNS:
        return [(f"product-{index}", product, "Portofoliu Focus") for index, product in enumerate(PRODUCTS, 1)]
    if module in {ModuleId.WORKFORCE, ModuleId.COMPENSATION}:
        store_codes = {store.site_code for store in stores}
        agents = [agent for agent in DEMO_AGENTS if agent.site_code in store_codes]
        return [
            (f"{agent.site_code}:{agent.name}", agent.name, f"{agent.site_code} · {agent.regional}")
            for agent in agents[:16]
        ]
    return [(store.site_code, store.label, f"{store.firm} · {store.regional}") for store in stores[:16]]


def _kpis(module: ModuleId, scope: AnalyticsScope, entity_count: int) -> list[KpiMetric]:
    rng = random.Random(_seed(module, scope, "kpis"))
    if module is ModuleId.SALES:
        sales = _number(PROFILES[module].base * Decimal(str(rng.uniform(0.78, 1.16))))
        target = _number(sales / Decimal(str(rng.uniform(0.87, 1.08))))
        receipts = _number(sales / Decimal(str(rng.uniform(88, 118))))
        return [
            KpiMetric(
                id="sales.total",
                label="Vânzări",
                value=sales,
                unit=MetricUnit.CURRENCY,
                delta_pct=_number(rng.uniform(-8, 14)),
                supporting_value=target,
                supporting_label="Target",
                risk=_risk(_number(sales * 100 / target)),
            ),
            KpiMetric(
                id="target.progress_pct",
                label="Realizare target",
                value=_number(sales * 100 / target),
                unit=MetricUnit.PERCENT,
                supporting_value=target,
                supporting_label="Target",
                risk=_risk(_number(sales * 100 / target)),
            ),
            KpiMetric(
                id="receipts.average_value",
                label="Valoare medie bon",
                value=_number(sales / receipts),
                unit=MetricUnit.CURRENCY,
                delta_pct=_number(rng.uniform(-4, 9)),
            ),
            KpiMetric(
                id="receipts.total",
                label="Bonuri",
                value=receipts,
                unit=MetricUnit.INTEGER,
                delta_pct=_number(rng.uniform(-6, 12)),
            ),
            KpiMetric(
                id="receipt_2plus_pct",
                label="Bonuri 2+",
                value=_number(rng.uniform(18, 42)),
                unit=MetricUnit.PERCENT,
                supporting_value=receipts,
                supporting_label="Bonuri",
            ),
        ]
    if module is ModuleId.PERFORMANCE:
        average = _number(rng.uniform(88, 104))
        at_target = _number(max(0, round(entity_count * float(average) / 110)))
        return [
            KpiMetric(
                id="performance.average",
                label="Realizare medie",
                value=average,
                unit=MetricUnit.PERCENT,
                risk=_risk(average),
            ),
            KpiMetric(
                id="performance.at_target",
                label="Entități la target",
                value=at_target,
                unit=MetricUnit.INTEGER,
                supporting_value=_number(entity_count),
                supporting_label="Entități analizate",
            ),
            KpiMetric(
                id="performance.volatility",
                label="Volatilitate",
                value=_number(rng.uniform(6, 18)),
                unit=MetricUnit.PERCENT,
                risk=RiskLevel.WATCH,
            ),
            KpiMetric(
                id="performance.daily_productivity",
                label="Productivitate / zi",
                value=_number(rng.uniform(3700, 6900)),
                unit=MetricUnit.CURRENCY,
                delta_pct=_number(rng.uniform(-7, 10)),
            ),
        ]
    if module is ModuleId.CAMPAIGNS:
        focus_sales = _number(PROFILES[module].base * Decimal(str(rng.uniform(0.8, 1.2))))
        return [
            KpiMetric(
                id="campaigns.focus_sales",
                label="Vânzări Focus",
                value=focus_sales,
                unit=MetricUnit.CURRENCY,
                delta_pct=_number(rng.uniform(-5, 16)),
            ),
            KpiMetric(
                id="campaigns.focus_share",
                label="Pondere Focus",
                value=_number(rng.uniform(18, 34)),
                unit=MetricUnit.PERCENT,
                risk=RiskLevel.HEALTHY,
            ),
            KpiMetric(
                id="campaigns.active_stores",
                label="Magazine active",
                value=_number(max(entity_count, 1)),
                unit=MetricUnit.INTEGER,
            ),
            KpiMetric(
                id="campaigns.active_products",
                label="Produse active",
                value=_number(max(3, round(entity_count * rng.uniform(1.2, 2.1)))),
                unit=MetricUnit.INTEGER,
            ),
        ]
    if module is ModuleId.WORKFORCE:
        headcount = _number(max(entity_count, 1))
        return [
            KpiMetric(
                id="workforce.headcount",
                label="Headcount activ",
                value=headcount,
                unit=MetricUnit.INTEGER,
            ),
            KpiMetric(
                id="workforce.productivity",
                label="Productivitate / agent",
                value=_number(rng.uniform(18500, 31500)),
                unit=MetricUnit.CURRENCY,
                delta_pct=_number(rng.uniform(-5, 11)),
            ),
            KpiMetric(
                id="workforce.coverage",
                label="Acoperire magazine",
                value=_number(rng.uniform(86, 100)),
                unit=MetricUnit.PERCENT,
                risk=RiskLevel.HEALTHY,
            ),
            KpiMetric(
                id="workforce.stability",
                label="Stabilitate 12 luni",
                value=_number(rng.uniform(72, 94)),
                unit=MetricUnit.PERCENT,
                risk=RiskLevel.WATCH,
            ),
        ]
    if module is ModuleId.COMPENSATION:
        payroll = _number(PROFILES[module].base * Decimal(str(rng.uniform(0.82, 1.14))))
        average = _number(payroll / Decimal(max(entity_count, 1)))
        return [
            KpiMetric(
                id="compensation.payroll",
                label="Cost salarial",
                value=payroll,
                unit=MetricUnit.CURRENCY,
                delta_pct=_number(rng.uniform(-3, 9)),
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
                value=_number(average * Decimal(str(rng.uniform(0.91, 0.98)))),
                unit=MetricUnit.CURRENCY,
            ),
            KpiMetric(
                id="compensation.sales_ratio",
                label="Cost / vânzări",
                value=_number(rng.uniform(17, 28)),
                unit=MetricUnit.PERCENT,
                risk=RiskLevel.WATCH,
            ),
        ]
    if module is ModuleId.FINANCE:
        revenue = _number(PROFILES[module].base * Decimal(str(rng.uniform(0.82, 1.15))))
        ebit = _number(revenue * Decimal(str(rng.uniform(0.08, 0.21))))
        return [
            KpiMetric(
                id="finance.revenue",
                label="Venit net",
                value=revenue,
                unit=MetricUnit.CURRENCY,
                delta_pct=_number(rng.uniform(-7, 13)),
            ),
            KpiMetric(
                id="finance.ebit",
                label="EBIT",
                value=ebit,
                unit=MetricUnit.CURRENCY,
                risk=RiskLevel.HEALTHY,
            ),
            KpiMetric(
                id="finance.ebit_margin",
                label="Marjă EBIT",
                value=_number(ebit * 100 / revenue),
                unit=MetricUnit.PERCENT,
                risk=RiskLevel.HEALTHY,
            ),
            KpiMetric(
                id="finance.operating_costs",
                label="Cost operațional",
                value=_number(revenue * Decimal(str(rng.uniform(0.36, 0.54)))),
                unit=MetricUnit.CURRENCY,
            ),
        ]
    forecast = _number(PROFILES[module].base * Decimal(str(rng.uniform(0.89, 1.11))))
    target = _number(forecast / Decimal(str(rng.uniform(0.91, 1.05))))
    return [
        KpiMetric(
            id="planning.forecast",
            label="Forecast",
            value=forecast,
            unit=MetricUnit.CURRENCY,
            supporting_value=target,
            supporting_label="Target",
            risk=_risk(_number(forecast * 100 / target)),
        ),
        KpiMetric(
            id="planning.target_gap",
            label="Gap față de target",
            value=_number(forecast - target),
            unit=MetricUnit.CURRENCY,
            risk=_risk(_number(forecast * 100 / target)),
        ),
        KpiMetric(
            id="planning.accuracy",
            label="Acuratețe forecast",
            value=_number(rng.uniform(86, 97)),
            unit=MetricUnit.PERCENT,
            risk=RiskLevel.HEALTHY,
        ),
        KpiMetric(
            id="planning.actual",
            label="Actual disponibil",
            value=_number(forecast * Decimal(str(rng.uniform(0.86, 1.02)))),
            unit=MetricUnit.CURRENCY,
        ),
    ]


def _trend(module: ModuleId, scope: AnalyticsScope) -> list[TrendPoint]:
    profile = PROFILES[module]
    rng = random.Random(_seed(module, scope, "trend"))
    result: list[TrendPoint] = []
    for index, offset in enumerate(range(-11, 1)):
        month = _shift_month(scope.period, offset)
        seasonal = Decimal(str(1 + 0.11 * math.sin((index + 1) / 2.2)))
        noise = Decimal(str(rng.uniform(0.91, 1.09)))
        primary = _number(profile.base * seasonal * noise)
        if module is ModuleId.PERFORMANCE:
            primary = _number(rng.uniform(84, 106))
        elif module is ModuleId.WORKFORCE:
            primary = _number(rng.uniform(30, 46))
        comparison = _number(primary / Decimal(str(rng.uniform(0.92, 1.08))))
        target = _number(primary / Decimal(str(rng.uniform(0.9, 1.06))))
        secondary = _number(primary * Decimal(str(rng.uniform(0.09, 0.28))))
        result.append(
            TrendPoint(
                key=month,
                label=month,
                primary=primary,
                comparison=comparison,
                target=target,
                secondary=secondary,
                is_estimate=offset == 0 and module in {ModuleId.FINANCE, ModuleId.PLANNING},
            )
        )
    return result


def _breakdown(module: ModuleId, scope: AnalyticsScope) -> list[BreakdownRow]:
    rng = random.Random(_seed(module, scope, "breakdown"))
    profile = PROFILES[module]
    entities = _entities(module, scope)
    rows: list[BreakdownRow] = []
    divisor = Decimal(max(len(entities), 1))
    for entity_id, label, context in entities:
        progress = _number(rng.uniform(68, 116))
        primary = _number(profile.base / divisor * Decimal(str(rng.uniform(0.62, 1.44))))
        if module is ModuleId.PERFORMANCE:
            primary = progress
        elif module is ModuleId.WORKFORCE:
            primary = _number(rng.uniform(1, 4))
        secondary = _number(primary * Decimal(str(rng.uniform(0.11, 0.42))))
        tertiary = _number(rng.uniform(4, 32))
        rows.append(
            BreakdownRow(
                id=entity_id,
                label=label,
                context=context,
                primary=primary,
                secondary=secondary,
                tertiary=tertiary,
                progress_pct=progress,
                delta_pct=_number(rng.uniform(-18, 19)),
                risk=_risk(progress),
            )
        )
    return sorted(rows, key=lambda row: row.progress_pct or Decimal(0))[:16]


def _distribution(module: ModuleId, scope: AnalyticsScope) -> list[DimensionShare]:
    profile = PROFILES[module]
    rng = random.Random(_seed(module, scope, "distribution"))
    weights = [Decimal(str(rng.uniform(0.5, 2.0))) for _ in profile.categories]
    total_weight = sum(weights, Decimal(0)) or Decimal(1)
    total_value = profile.base
    allocated = Decimal(0)
    result: list[DimensionShare] = []
    for index, (label, weight) in enumerate(zip(profile.categories, weights, strict=True)):
        value = total_value - allocated if index == len(weights) - 1 else _number(total_value * weight / total_weight)
        allocated += value
        result.append(
            DimensionShare(
                id=f"{module.value}-{index}",
                label=label,
                value=value,
                share_pct=_number(value * 100 / total_value),
            )
        )
    return sorted(result, key=lambda item: item.value, reverse=True)


def _matrix(module: ModuleId, scope: AnalyticsScope, rows: list[BreakdownRow]) -> list[MatrixCell]:
    rng = random.Random(_seed(module, scope, "matrix"))
    months = [_shift_month(scope.period, offset) for offset in range(-5, 1)]
    result: list[MatrixCell] = []
    for row in rows[:6]:
        for month in months:
            value = _number(rng.uniform(68, 116))
            result.append(
                MatrixCell(
                    x=month,
                    y=row.label,
                    value=value,
                    label=f"{value}%",
                    risk=_risk(value),
                )
            )
    return result


def _alerts(module: ModuleId, rows: list[BreakdownRow]) -> list[InsightAlert]:
    alerts = [
        InsightAlert(
            id=f"{module.value}-demo-contract",
            severity=AlertSeverity.INFO,
            title="Date demo deterministe",
            description="Structura și interacțiunile sunt reale; valorile vor fi reconciliate la conectarea PostgreSQL.",
        )
    ]
    for row in rows:
        if row.risk is RiskLevel.RISK:
            alerts.append(
                InsightAlert(
                    id=f"{module.value}-risk-{row.id}",
                    severity=AlertSeverity.WARNING,
                    title="Entitate sub pragul de atenție",
                    description=f"Indicatorul de progres este {row.progress_pct}% în perioada selectată.",
                    entity_label=row.label,
                )
            )
        if len(alerts) >= 5:
            break
    return alerts


class DemoInsightRepository(DemoAnalyticsRepository):
    async def get_module(
        self,
        module: ModuleId,
        scope: AnalyticsScope,
    ) -> ModuleAnalyticsResponse:
        profile = PROFILES[module]
        rows = _breakdown(module, scope)
        snapshot = await self.resolve_snapshot(scope)
        domain = {
            ModuleId.SALES: SourceDomain.SALES,
            ModuleId.PERFORMANCE: SourceDomain.SALES,
            ModuleId.CAMPAIGNS: SourceDomain.CAMPAIGNS,
            ModuleId.WORKFORCE: SourceDomain.WORKFORCE,
            ModuleId.COMPENSATION: SourceDomain.COMPENSATION,
            ModuleId.FINANCE: SourceDomain.FINANCE,
            ModuleId.PLANNING: SourceDomain.PLANNING,
        }[module]
        source_meta = snapshot.sources[domain.value]
        meta = _meta(module, scope).model_copy(
            update={
                "analytical_snapshot_id": snapshot.id,
                "snapshot_contract_version": snapshot.contract_version,
                "sources": {domain: source_meta},
                "source": source_meta.source,
                "as_of": source_meta.as_of,
                "is_final": source_meta.is_final,
            }
        )
        return ModuleAnalyticsResponse(
            meta=meta,
            module=module,
            title=profile.title,
            description=profile.description,
            required_capability=profile.capability,
            axes=profile.axes,
            supported_charts=profile.charts,
            kpis=_kpis(module, scope, len(rows)),
            trend=_trend(module, scope),
            distribution=_distribution(module, scope),
            breakdown=rows,
            matrix=_matrix(module, scope, rows),
            alerts=_alerts(module, rows),
        )
