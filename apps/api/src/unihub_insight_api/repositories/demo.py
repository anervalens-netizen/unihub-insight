from __future__ import annotations

import calendar
import hashlib
import math
import random
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from unihub_insight_api.domain import (
    AlertSeverity,
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
)
from unihub_insight_api.services import previous_period, scope_label

MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")
BUCHAREST = ZoneInfo("Europe/Bucharest")


def _decimal(value: int | float | str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value: int | float | str | Decimal) -> Decimal:
    return _decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _percent(value: int | float | str | Decimal) -> Decimal:
    return _decimal(value).quantize(PERCENT, rounding=ROUND_HALF_UP)


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


def _shift_month(period: str, offset: int) -> str:
    year, month = (int(part) for part in period.split("-"))
    absolute = year * 12 + month - 1 + offset
    next_year, zero_month = divmod(absolute, 12)
    return f"{next_year:04d}-{zero_month + 1:02d}"


def _business_today() -> date:
    return datetime.now(BUCHAREST).date()


def _current_period() -> str:
    today = _business_today()
    return f"{today.year:04d}-{today.month:02d}"


def _seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


DEMO_STORES: tuple[FilterStore, ...] = (
    FilterStore(
        site_code="B001",
        label="București Plaza",
        firm="MOBIUP",
        regional="Andrei Sud",
        asm="ASM București",
    ),
    FilterStore(
        site_code="B002",
        label="București ParkLake",
        firm="MOBIUP",
        regional="Andrei Sud",
        asm="ASM București",
    ),
    FilterStore(
        site_code="B003",
        label="București Sun Plaza",
        firm="MOBICELL",
        regional="Andrei Sud",
        asm="ASM București",
    ),
    FilterStore(
        site_code="C001",
        label="Constanța City",
        firm="MOBIUP",
        regional="Dobrogea",
        asm="ASM Constanța",
    ),
    FilterStore(
        site_code="C002",
        label="Constanța VIVO",
        firm="MOBICELL",
        regional="Dobrogea",
        asm="ASM Constanța",
    ),
    FilterStore(
        site_code="G001",
        label="Galați Shopping",
        firm="MOBIUP",
        regional="Dobrogea",
        asm="ASM Galați",
    ),
    FilterStore(
        site_code="BZR1",
        label="Buzău Aurora",
        firm="MOBICELL",
        regional="Moldova Sud",
        asm="ASM Buzău",
    ),
    FilterStore(
        site_code="BR01",
        label="Brăila Mall",
        firm="MOBIUP",
        regional="Moldova Sud",
        asm="ASM Brăila",
    ),
    FilterStore(
        site_code="P001",
        label="Ploiești Shopping",
        firm="MOBIUP",
        regional="Muntenia",
        asm="ASM Prahova",
    ),
    FilterStore(
        site_code="P002",
        label="Ploiești AFI",
        firm="MOBICELL",
        regional="Muntenia",
        asm="ASM Prahova",
    ),
    FilterStore(
        site_code="T001",
        label="Târgoviște Dâmbovița",
        firm="MOBIUP",
        regional="Muntenia",
        asm="ASM Dâmbovița",
    ),
    FilterStore(
        site_code="F001",
        label="Focșani Mall",
        firm="MOBICELL",
        regional="Moldova Sud",
        asm="ASM Vrancea",
    ),
)

DEMO_AGENTS: tuple[FilterAgent, ...] = tuple(
    FilterAgent(
        name=f"Agent {index:02d}",
        site_code=store.site_code,
        firm=store.firm,
        regional=store.regional,
        asm=store.asm,
    )
    for index, store in enumerate(DEMO_STORES * 2, start=1)
)


class DemoAnalyticsRepository:
    async def get_filter_options(self, period: str) -> FilterOptionsResponse:
        current = _current_period()
        periods = [_shift_month(current, -offset) for offset in range(0, 24)]
        if period not in periods:
            periods.insert(0, period)
        return FilterOptionsResponse(
            periods=periods,
            firms=sorted({store.firm for store in DEMO_STORES}),
            regionals=sorted({store.regional for store in DEMO_STORES}),
            asms=sorted({store.asm for store in DEMO_STORES if store.asm}),
            stores=list(DEMO_STORES),
            agents=list(DEMO_AGENTS),
            data_mode=DataMode.DEMO,
        )

    async def get_overview(self, scope: AnalyticsScope) -> OverviewResponse:
        selected_stores = self._selected_stores(scope)
        store_count = max(len(selected_stores), 1)
        rng = random.Random(_seed(scope.period, scope.model_dump_json()))
        year, month = (int(part) for part in scope.period.split("-"))
        days_in_month = calendar.monthrange(year, month)[1]
        today = _business_today()
        current_period = _current_period()
        is_final = scope.period < current_period
        if is_final:
            cutoff_day = days_in_month
        elif scope.period == current_period:
            cutoff_day = min(today.day, days_in_month)
        else:
            cutoff_day = 0

        target_total = _money(store_count * rng.uniform(72_000, 96_000))
        final_progress = Decimal(str(rng.uniform(0.87, 1.09)))
        expected_final_sales = _money(target_total * final_progress)
        covered_ratio = (
            Decimal(cutoff_day) / Decimal(days_in_month) if days_in_month else Decimal(0)
        )
        total_sales = (
            expected_final_sales if is_final else _money(expected_final_sales * covered_ratio)
        )
        forecast = (
            _money(total_sales / Decimal(cutoff_day) * Decimal(days_in_month))
            if cutoff_day > 0 and not is_final
            else total_sales
        )
        target_progress = (
            _percent(total_sales * Decimal("100") / target_total) if target_total > 0 else None
        )
        forecast_progress = (
            _percent(forecast * Decimal("100") / target_total) if target_total > 0 else None
        )

        comparison_factor = Decimal(str(rng.uniform(0.89, 1.08)))
        previous_sales = (
            _money(total_sales / comparison_factor) if comparison_factor else Decimal(0)
        )
        sales_delta = _delta(total_sales, previous_sales)
        receipt_count = max(int(total_sales / Decimal(str(rng.uniform(85, 120)))), 0)
        receipt_2plus_pct = _percent(rng.uniform(23, 41)) if receipt_count else Decimal(0)

        cumulative = Decimal(0)
        full_daily: list[Decimal] = []
        for day in range(1, max(cutoff_day, 1) + 1):
            weekday = date(year, month, min(day, days_in_month)).weekday()
            weekday_factor = 0.78 if weekday == 0 else 1.18 if weekday >= 5 else 1.0
            seasonal = 1 + 0.14 * math.sin(day / 4.3)
            increment = max(0.1, weekday_factor * seasonal * rng.uniform(0.76, 1.25))
            full_daily.append(_decimal(increment))
        weight_total = sum(full_daily, Decimal(0)) or Decimal(1)

        daily_points: list[DailyPoint] = []
        for day in range(1, days_in_month + 1):
            actual: Decimal | None = None
            if cutoff_day > 0 and day <= cutoff_day:
                cumulative += total_sales * full_daily[day - 1] / weight_total
                actual = _money(total_sales if day == cutoff_day else cumulative)
            target_pace = _money(target_total * Decimal(day) / Decimal(days_in_month))
            projected = None
            if cutoff_day > 0 and not is_final and day >= cutoff_day:
                projected = _money(total_sales / Decimal(cutoff_day) * Decimal(day))
            comparison_base = actual if actual is not None else target_pace * comparison_factor
            comparison = _money(comparison_base / comparison_factor)
            daily_points.append(
                DailyPoint(
                    day=day,
                    sales=actual,
                    target_pace=target_pace,
                    forecast=projected,
                    comparison=comparison,
                )
            )

        performance = self._performance_rows(
            selected_stores,
            target_total,
            total_sales,
            scope,
        )
        contribution = self._contribution(selected_stores, total_sales)
        alerts = self._alerts(forecast_progress, performance, cutoff_day)

        as_of = date(year, month, cutoff_day) if cutoff_day > 0 else None
        return OverviewResponse(
            meta=OverviewMeta(
                period=scope.period,
                comparison=scope.comparison,
                as_of=as_of,
                is_final=is_final,
                data_mode=DataMode.DEMO,
                scope_label=scope_label(scope),
                generated_at=datetime.now(UTC),
                source="deterministic-demo",
            ),
            kpis=[
                KpiMetric(
                    id="sales.total",
                    label="Vânzări",
                    value=total_sales,
                    unit=MetricUnit.CURRENCY,
                    delta_pct=sales_delta
                    if previous_period(scope.period, scope.comparison)
                    else None,
                    delta_label="față de reper",
                    risk=(
                        RiskLevel.HEALTHY
                        if sales_delta is not None and sales_delta >= 0
                        else RiskLevel.WATCH
                    ),
                    supporting_value=_money(total_sales / Decimal(max(cutoff_day, 1))),
                    supporting_label="Medie / zi acoperită",
                ),
                KpiMetric(
                    id="target.progress_pct",
                    label="Realizare target",
                    value=target_progress or Decimal(0),
                    unit=MetricUnit.PERCENT,
                    risk=_risk(forecast_progress),
                    supporting_value=target_total,
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
                    risk=(
                        RiskLevel.HEALTHY if receipt_2plus_pct >= Decimal("32") else RiskLevel.WATCH
                    ),
                    supporting_value=Decimal(receipt_count),
                    supporting_label="Bonuri totale",
                ),
            ],
            daily=daily_points,
            contribution=contribution,
            performance=performance,
            alerts=alerts,
        )

    @staticmethod
    def _selected_stores(scope: AnalyticsScope) -> list[FilterStore]:
        stores = list(DEMO_STORES)
        if scope.stores:
            selected = set(scope.stores)
            return [store for store in stores if store.site_code in selected]
        if scope.firm:
            stores = [store for store in stores if store.firm == scope.firm]
        if scope.regional:
            stores = [store for store in stores if store.regional == scope.regional]
        if scope.asm:
            stores = [store for store in stores if store.asm == scope.asm]
        if scope.agent:
            site_codes = {agent.site_code for agent in DEMO_AGENTS if agent.name == scope.agent}
            stores = [store for store in stores if store.site_code in site_codes]
        return stores

    @staticmethod
    def _contribution(stores: list[FilterStore], total_sales: Decimal) -> list[DimensionShare]:
        if not stores or total_sales <= 0:
            return []
        firm_counts: dict[str, int] = {}
        for store in stores:
            firm_counts[store.firm] = firm_counts.get(store.firm, 0) + 1
        count_total = sum(firm_counts.values())
        result: list[DimensionShare] = []
        allocated = Decimal(0)
        for index, (firm, count) in enumerate(sorted(firm_counts.items())):
            if index == len(firm_counts) - 1:
                value = total_sales - allocated
            else:
                value = _money(total_sales * Decimal(count) / Decimal(count_total))
                allocated += value
            result.append(
                DimensionShare(
                    id=firm.lower(),
                    label=firm,
                    value=value,
                    share_pct=_percent(value * Decimal("100") / total_sales),
                )
            )
        return result

    @staticmethod
    def _performance_rows(
        stores: list[FilterStore],
        target_total: Decimal,
        sales_total: Decimal,
        scope: AnalyticsScope,
    ) -> list[PerformanceRow]:
        if not stores:
            return []
        rng = random.Random(_seed("performance", scope.period, scope.model_dump_json()))
        raw_weights = [Decimal(str(rng.uniform(0.7, 1.35))) for _ in stores]
        weight_total = sum(raw_weights, Decimal(0)) or Decimal(1)
        rows: list[PerformanceRow] = []
        for store, weight in zip(stores, raw_weights, strict=True):
            target = _money(target_total / Decimal(len(stores)))
            sales = _money(sales_total * weight / weight_total)
            progress = _percent(sales * Decimal("100") / target) if target > 0 else None
            benchmark = _money(sales / Decimal(str(rng.uniform(0.88, 1.12))))
            rows.append(
                PerformanceRow(
                    id=store.site_code,
                    label=store.label,
                    context=f"{store.firm} · {store.regional}",
                    sales=sales,
                    target=target,
                    progress_pct=progress,
                    delta_pct=_delta(sales, benchmark),
                    risk=_risk(progress),
                )
            )
        return sorted(
            rows,
            key=lambda row: row.progress_pct if row.progress_pct is not None else Decimal(-1),
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
                    description="Perioada selectată nu are un cutoff de vânzări disponibil.",
                )
            )
        if forecast_progress is not None and forecast_progress < Decimal("95"):
            alerts.append(
                InsightAlert(
                    id="forecast-gap",
                    severity=(
                        AlertSeverity.CRITICAL
                        if forecast_progress < Decimal("85")
                        else AlertSeverity.WARNING
                    ),
                    title="Forecast sub target",
                    description=(
                        f"Run-rate-ul curent indică {forecast_progress}% din target. "
                        "Forecastul este liniar și trebuie interpretat împreună cu sezonalitatea."
                    ),
                )
            )
        for row in performance:
            if row.risk is RiskLevel.RISK:
                alerts.append(
                    InsightAlert(
                        id=f"store-risk-{row.id}",
                        severity=AlertSeverity.WARNING,
                        title="Magazin sub ritmul necesar",
                        description=(
                            f"Realizarea este {row.progress_pct}% pentru perioada acoperită."
                        ),
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
                    description="Regulile inițiale nu au detectat un risc comercial major în scope.",
                )
            )
        return alerts
