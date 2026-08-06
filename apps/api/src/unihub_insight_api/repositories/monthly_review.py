from __future__ import annotations

import asyncio
import hashlib
import math
import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from unihub_insight_api.domain import (
    AlertSeverity,
    AnalyticsScope,
    DataMode,
    InsightAlert,
    MetricUnit,
    OverviewMeta,
)
from unihub_insight_api.domain.monthly_review import (
    ComparisonMetric,
    DeltaKind,
    DriverBridge,
    MonthlyReviewResponse,
    MonthlyTrendPoint,
    PerformanceReviewRow,
    ProductReviewRow,
    ReturnReviewRow,
    ReviewStatus,
    SeasonalityPoint,
)
from unihub_insight_api.repositories.demo import DEMO_AGENTS
from unihub_insight_api.repositories.demo_modules import DemoInsightRepository
from unihub_insight_api.repositories.postgres import _delta, _money, _percent, _ratio
from unihub_insight_api.repositories.postgres_hardened import (
    PostgresHardenedInsightRepository,
)
from unihub_insight_api.services import scope_label

ZERO = Decimal(0)
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class Aggregate:
    sales: Decimal = ZERO
    units: Decimal = ZERO
    receipts: Decimal = ZERO
    receipt_2plus: Decimal = ZERO
    focus_units: Decimal = ZERO
    gross_sales: Decimal = ZERO
    return_value: Decimal = ZERO
    working_days: Decimal = ZERO
    target: Decimal = ZERO

    def __add__(self, other: Aggregate) -> Aggregate:
        return Aggregate(
            sales=self.sales + other.sales,
            units=self.units + other.units,
            receipts=self.receipts + other.receipts,
            receipt_2plus=self.receipt_2plus + other.receipt_2plus,
            focus_units=self.focus_units + other.focus_units,
            gross_sales=self.gross_sales + other.gross_sales,
            return_value=self.return_value + other.return_value,
            working_days=self.working_days + other.working_days,
            target=self.target + other.target,
        )

    def divided(self, divisor: int) -> Aggregate:
        if divisor <= 0:
            return Aggregate()
        value = Decimal(divisor)
        return Aggregate(
            sales=self.sales / value,
            units=self.units / value,
            receipts=self.receipts / value,
            receipt_2plus=self.receipt_2plus / value,
            focus_units=self.focus_units / value,
            gross_sales=self.gross_sales / value,
            return_value=self.return_value / value,
            working_days=self.working_days / value,
            target=self.target / value,
        )

    @property
    def average_receipt(self) -> Decimal | None:
        return _money(self.sales / self.receipts) if self.receipts > 0 else None

    @property
    def units_per_receipt(self) -> Decimal | None:
        return _percent(self.units / self.receipts) if self.receipts > 0 else None

    @property
    def value_per_unit(self) -> Decimal | None:
        return _money(self.sales / self.units) if self.units > 0 else None

    @property
    def bon2acc_pct(self) -> Decimal | None:
        return _ratio(self.receipt_2plus, self.receipts)

    @property
    def focus_pct(self) -> Decimal | None:
        return _ratio(self.focus_units, self.units)

    @property
    def return_rate_pct(self) -> Decimal | None:
        return _ratio(self.return_value, self.gross_sales)


@dataclass(frozen=True)
class Entity:
    id: str
    label: str
    context: str
    entity_type: str


@dataclass(frozen=True)
class ProductEntity:
    id: str
    label: str
    brand: str
    category: str


def shift_month(period: str, offset: int) -> str:
    year, month = (int(part) for part in period.split("-"))
    absolute = year * 12 + month - 1 + offset
    next_year, zero_month = divmod(absolute, 12)
    return f"{next_year:04d}-{zero_month + 1:02d}"


def unique_periods(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def average(values: Iterable[Aggregate], divisor: int) -> Aggregate:
    total = Aggregate()
    for value in values:
        total += value
    return total.divided(divisor)


def optional_delta(current: Decimal | None, baseline: Decimal | None) -> Decimal | None:
    if current is None or baseline is None or baseline == 0:
        return None
    return _delta(current, baseline)


def point_delta(current: Decimal | None, baseline: Decimal | None) -> Decimal | None:
    if current is None or baseline is None:
        return None
    return _percent(current - baseline)


def bounded(value: Decimal, minimum: Decimal = ZERO, maximum: Decimal = HUNDRED) -> Decimal:
    return min(max(value, minimum), maximum)


def consistency_score(values: Sequence[Decimal]) -> Decimal:
    non_zero = [float(value) for value in values if value > 0]
    if len(non_zero) < 2:
        return ZERO
    mean = sum(non_zero) / len(non_zero)
    if mean <= 0:
        return ZERO
    variance = sum((value - mean) ** 2 for value in non_zero) / len(non_zero)
    coefficient = math.sqrt(variance) / mean
    return _percent(bounded(Decimal(str(100 - coefficient * 100))))


def classify_status(
    *,
    current: Decimal,
    previous_year: Decimal,
    recent_average: Decimal,
    target_pct: Decimal | None,
    yoy_pct: Decimal | None,
    recent_pct: Decimal | None,
    consistency: Decimal,
) -> ReviewStatus:
    if current > 0 and previous_year == 0 and recent_average == 0:
        return ReviewStatus.NEW
    if current == 0 and (previous_year > 0 or recent_average > 0):
        return ReviewStatus.EXITED
    if target_pct is not None and target_pct >= HUNDRED and (yoy_pct or ZERO) >= 0 and (recent_pct or ZERO) >= 0:
        return ReviewStatus.OUTPERFORMING
    if target_pct is not None and target_pct < Decimal("85") and (yoy_pct or ZERO) < 0 and (recent_pct or ZERO) < 0:
        return ReviewStatus.RISK
    if yoy_pct is not None and recent_pct is not None:
        if yoy_pct < 0 and recent_pct >= Decimal("5"):
            return ReviewStatus.RECOVERING
        if yoy_pct >= 0 and recent_pct <= Decimal("-5"):
            return ReviewStatus.SLOWING
    if consistency < Decimal("65"):
        return ReviewStatus.VOLATILE
    if (
        (target_pct is not None and target_pct < Decimal("95"))
        or (yoy_pct is not None and yoy_pct < Decimal("-5"))
        or (recent_pct is not None and recent_pct < Decimal("-5"))
    ):
        return ReviewStatus.WATCH
    return ReviewStatus.HEALTHY


def score_entity(
    *,
    target_pct: Decimal | None,
    yoy_pct: Decimal | None,
    recent_pct: Decimal | None,
    consistency: Decimal,
) -> Decimal:
    target_component = (
        bounded((target_pct or Decimal("90")) / Decimal("1.2")) if target_pct is not None else Decimal("75")
    )
    yoy_component = bounded(Decimal("50") + (yoy_pct or ZERO) * Decimal("1.8"))
    recent_component = bounded(Decimal("50") + (recent_pct or ZERO) * Decimal("2.2"))
    score = (
        target_component * Decimal("0.40")
        + yoy_component * Decimal("0.25")
        + recent_component * Decimal("0.25")
        + consistency * Decimal("0.10")
    )
    return _percent(bounded(score))


def bridge(current: Aggregate, baseline: Aggregate, basis: str) -> DriverBridge:
    current_receipts = current.receipts
    baseline_receipts = baseline.receipts
    current_upr = current.units_per_receipt or ZERO
    baseline_upr = baseline.units_per_receipt or ZERO
    current_vpu = current.value_per_unit or ZERO
    baseline_vpu = baseline.value_per_unit or ZERO
    receipts_effect = _money((current_receipts - baseline_receipts) * baseline_upr * baseline_vpu)
    units_effect = _money(current_receipts * (current_upr - baseline_upr) * baseline_vpu)
    value_effect = _money(current_receipts * current_upr * (current_vpu - baseline_vpu))
    difference = _money(current.sales - baseline.sales)
    correction = difference - receipts_effect - units_effect - value_effect
    value_effect = _money(value_effect + correction)
    return DriverBridge(
        basis=basis,
        baseline_sales=_money(baseline.sales),
        current_sales=_money(current.sales),
        sales_difference=difference,
        receipts_effect=receipts_effect,
        units_per_receipt_effect=units_effect,
        value_per_unit_effect=value_effect,
    )


def primary_driver(current: Aggregate, baseline: Aggregate) -> tuple[str, Decimal]:
    result = bridge(current, baseline, "entity")
    effects = {
        "Bonuri": result.receipts_effect,
        "Produse / bon": result.units_per_receipt_effect,
        "Valoare / produs și mix": result.value_per_unit_effect,
    }
    return max(effects.items(), key=lambda item: abs(item[1]))


def make_metric(
    metric_id: str,
    label: str,
    unit: MetricUnit,
    current: Decimal | None,
    previous_year: Decimal | None,
    previous_month: Decimal | None,
    recent_average: Decimal | None,
    *,
    target: Decimal | None = None,
    points: bool = False,
) -> ComparisonMetric:
    current_value = current or ZERO
    delta = point_delta if points else optional_delta
    return ComparisonMetric(
        id=metric_id,
        label=label,
        unit=unit,
        current=_money(current_value) if unit is MetricUnit.CURRENCY else _percent(current_value),
        previous_year=previous_year,
        previous_month=previous_month,
        recent_average=recent_average,
        target=target,
        yoy_delta=delta(current, previous_year),
        mom_delta=delta(current, previous_month),
        recent_delta=delta(current, recent_average),
        target_delta=delta(current, target),
        delta_kind=(DeltaKind.PERCENTAGE_POINTS if points else DeltaKind.PERCENT),
    )


def review_row(
    entity: Entity,
    current: Aggregate,
    previous_year: Aggregate,
    previous_month: Aggregate,
    recent_average: Aggregate,
    recent_series: Sequence[Decimal],
) -> PerformanceReviewRow:
    target_pct = _ratio(current.sales, current.target)
    yoy_pct = optional_delta(current.sales, previous_year.sales)
    mom_pct = optional_delta(current.sales, previous_month.sales)
    recent_pct = optional_delta(current.sales, recent_average.sales)
    consistency = consistency_score(recent_series)
    status = classify_status(
        current=current.sales,
        previous_year=previous_year.sales,
        recent_average=recent_average.sales,
        target_pct=target_pct,
        yoy_pct=yoy_pct,
        recent_pct=recent_pct,
        consistency=consistency,
    )
    if abs(current.sales - recent_average.sales) >= abs(current.sales - previous_year.sales):
        driver_basis = "media recentă"
        driver, impact = primary_driver(current, recent_average)
    else:
        driver_basis = "anul trecut"
        driver, impact = primary_driver(current, previous_year)
    return PerformanceReviewRow(
        id=entity.id,
        label=entity.label,
        context=entity.context,
        entity_type=entity.entity_type,
        sales=_money(current.sales),
        units=_percent(current.units),
        receipts=_percent(current.receipts),
        target=_money(current.target) if current.target > 0 else None,
        target_pct=target_pct,
        previous_year_sales=_money(previous_year.sales),
        previous_month_sales=_money(previous_month.sales),
        recent_average_sales=_money(recent_average.sales),
        yoy_pct=yoy_pct,
        mom_pct=mom_pct,
        recent_pct=recent_pct,
        average_receipt=current.average_receipt,
        units_per_receipt=current.units_per_receipt,
        value_per_unit=current.value_per_unit,
        bon2acc_pct=current.bon2acc_pct,
        focus_pct=current.focus_pct,
        return_rate_pct=current.return_rate_pct,
        working_days=_percent(current.working_days),
        consistency_pct=consistency,
        performance_score=score_entity(
            target_pct=target_pct,
            yoy_pct=yoy_pct,
            recent_pct=recent_pct,
            consistency=consistency,
        ),
        status=status,
        primary_driver=driver,
        primary_driver_impact=impact,
        driver_basis=driver_basis,
    )


def product_status(
    current: Aggregate,
    previous_year: Aggregate,
    recent_average: Aggregate,
) -> ReviewStatus:
    yoy = optional_delta(current.sales, previous_year.sales)
    recent = optional_delta(current.sales, recent_average.sales)
    if current.sales > 0 and previous_year.sales == 0 and recent_average.sales == 0:
        return ReviewStatus.NEW
    if current.sales == 0 and (previous_year.sales > 0 or recent_average.sales > 0):
        return ReviewStatus.EXITED
    if (yoy or ZERO) >= 10 and (recent or ZERO) >= 10:
        return ReviewStatus.OUTPERFORMING
    if (yoy or ZERO) <= -20 and (recent or ZERO) <= -20:
        return ReviewStatus.RISK
    if yoy is not None and recent is not None and yoy < 0 < recent:
        return ReviewStatus.RECOVERING
    if yoy is not None and recent is not None and yoy >= 0 > recent:
        return ReviewStatus.SLOWING
    if (yoy or ZERO) < -5 or (recent or ZERO) < -5:
        return ReviewStatus.WATCH
    return ReviewStatus.HEALTHY


def product_row(
    entity: ProductEntity,
    current: Aggregate,
    previous_year: Aggregate,
    recent_average: Aggregate,
    current_distribution: int | None,
    previous_year_distribution: int | None,
) -> ProductReviewRow:
    impact_yoy = _money(current.sales - previous_year.sales)
    impact_recent = _money(current.sales - recent_average.sales)
    score = _money(abs(impact_yoy) + abs(impact_recent))
    return ProductReviewRow(
        id=entity.id,
        label=entity.label,
        brand=entity.brand,
        category=entity.category,
        sales=_money(current.sales),
        previous_year_sales=_money(previous_year.sales),
        recent_average_sales=_money(recent_average.sales),
        yoy_pct=optional_delta(current.sales, previous_year.sales),
        recent_pct=optional_delta(current.sales, recent_average.sales),
        units=_percent(current.units),
        previous_year_units=_percent(previous_year.units),
        distribution=current_distribution,
        previous_year_distribution=previous_year_distribution,
        return_rate_pct=current.return_rate_pct,
        previous_year_return_rate_pct=previous_year.return_rate_pct,
        impact_yoy=impact_yoy,
        impact_recent=impact_recent,
        score=score,
        status=product_status(current, previous_year, recent_average),
    )


def return_status(
    current_rate: Decimal | None,
    previous_rate: Decimal | None,
    recent_rate: Decimal | None,
) -> ReviewStatus:
    current = current_rate or ZERO
    benchmark = max(previous_rate or ZERO, recent_rate or ZERO)
    if current >= Decimal("4") and current - benchmark >= Decimal("1"):
        return ReviewStatus.RISK
    if current >= Decimal("2") or current - benchmark >= Decimal("0.5"):
        return ReviewStatus.WATCH
    return ReviewStatus.HEALTHY


def return_row(
    *,
    entity_id: str,
    label: str,
    context: str,
    entity_type: str,
    current: Aggregate,
    previous_year: Aggregate,
    recent_average: Aggregate,
) -> ReturnReviewRow:
    return ReturnReviewRow(
        id=entity_id,
        label=label,
        context=context,
        entity_type=entity_type,
        current_value=_money(current.return_value),
        previous_year_value=_money(previous_year.return_value),
        recent_average_value=_money(recent_average.return_value),
        current_rate_pct=current.return_rate_pct,
        previous_year_rate_pct=previous_year.return_rate_pct,
        recent_rate_pct=recent_average.return_rate_pct,
        yoy_rate_delta_pp=point_delta(current.return_rate_pct, previous_year.return_rate_pct),
        recent_rate_delta_pp=point_delta(current.return_rate_pct, recent_average.return_rate_pct),
        status=return_status(
            current.return_rate_pct,
            previous_year.return_rate_pct,
            recent_average.return_rate_pct,
        ),
    )


def aggregate_groups(
    rows: dict[tuple[str, str], Aggregate],
    groups: dict[str, list[str]],
    periods: Sequence[str],
) -> dict[tuple[str, str], Aggregate]:
    result: dict[tuple[str, str], Aggregate] = {}
    for group_id, entity_ids in groups.items():
        for period in periods:
            total = Aggregate()
            for entity_id in entity_ids:
                total += rows.get((period, entity_id), Aggregate())
            result[(period, group_id)] = total
    return result


def build_rows(
    *,
    entities: Sequence[Entity],
    values: dict[tuple[str, str], Aggregate],
    period: str,
    previous_year_period: str,
    previous_month_period: str,
    recent_periods: Sequence[str],
) -> list[PerformanceReviewRow]:
    result: list[PerformanceReviewRow] = []
    for entity in entities:
        current = values.get((period, entity.id), Aggregate())
        previous_year = values.get((previous_year_period, entity.id), Aggregate())
        previous_month = values.get((previous_month_period, entity.id), Aggregate())
        recent_values = [values.get((item, entity.id), Aggregate()) for item in recent_periods]
        recent_average = average(recent_values, len(recent_periods))
        result.append(
            review_row(
                entity,
                current,
                previous_year,
                previous_month,
                recent_average,
                [item.sales for item in recent_values],
            )
        )
    return sorted(result, key=lambda item: (item.performance_score, item.sales))


def seasonality_points(
    values: dict[tuple[str, str], Aggregate],
    period: str,
    store_count: int,
) -> list[SeasonalityPoint]:
    result: list[SeasonalityPoint] = []
    for year_offset in range(2, -1, -1):
        current_period = shift_month(period, -12 * year_offset)
        previous_period = shift_month(current_period, -1)
        current = values.get((current_period, "network"), Aggregate())
        previous = values.get((previous_period, "network"), Aggregate())
        current_productivity = current.sales / current.working_days if current.working_days > 0 else None
        previous_productivity = previous.sales / previous.working_days if previous.working_days > 0 else None
        result.append(
            SeasonalityPoint(
                year=int(current_period[:4]),
                previous_period=previous_period,
                current_period=current_period,
                sales_lift_pct=optional_delta(current.sales, previous.sales),
                units_lift_pct=optional_delta(current.units, previous.units),
                receipts_lift_pct=optional_delta(current.receipts, previous.receipts),
                sales_per_store_day_lift_pct=optional_delta(
                    current_productivity,
                    previous_productivity,
                ),
                store_count=store_count,
                is_current=year_offset == 0,
            )
        )
    return result


def executive_metrics(
    current: Aggregate,
    previous_year: Aggregate,
    previous_month: Aggregate,
    recent_average: Aggregate,
) -> list[ComparisonMetric]:
    return [
        make_metric(
            "sales",
            "Vânzări",
            MetricUnit.CURRENCY,
            current.sales,
            previous_year.sales,
            previous_month.sales,
            recent_average.sales,
            target=current.target,
        ),
        make_metric(
            "units",
            "Unități",
            MetricUnit.INTEGER,
            current.units,
            previous_year.units,
            previous_month.units,
            recent_average.units,
        ),
        make_metric(
            "receipts",
            "Bonuri",
            MetricUnit.INTEGER,
            current.receipts,
            previous_year.receipts,
            previous_month.receipts,
            recent_average.receipts,
        ),
        make_metric(
            "average_receipt",
            "Valoare medie bon",
            MetricUnit.CURRENCY,
            current.average_receipt,
            previous_year.average_receipt,
            previous_month.average_receipt,
            recent_average.average_receipt,
        ),
        make_metric(
            "units_per_receipt",
            "Produse / bon",
            MetricUnit.DECIMAL,
            current.units_per_receipt,
            previous_year.units_per_receipt,
            previous_month.units_per_receipt,
            recent_average.units_per_receipt,
        ),
        make_metric(
            "value_per_unit",
            "Valoare / produs",
            MetricUnit.CURRENCY,
            current.value_per_unit,
            previous_year.value_per_unit,
            previous_month.value_per_unit,
            recent_average.value_per_unit,
        ),
        make_metric(
            "bon2acc",
            "Bonuri cu 2+ accesorii",
            MetricUnit.PERCENT,
            current.bon2acc_pct,
            previous_year.bon2acc_pct,
            previous_month.bon2acc_pct,
            recent_average.bon2acc_pct,
            points=True,
        ),
        make_metric(
            "focus",
            "Pondere Focus",
            MetricUnit.PERCENT,
            current.focus_pct,
            previous_year.focus_pct,
            previous_month.focus_pct,
            recent_average.focus_pct,
            points=True,
        ),
        make_metric(
            "returns",
            "Rată retur",
            MetricUnit.PERCENT,
            current.return_rate_pct,
            previous_year.return_rate_pct,
            previous_month.return_rate_pct,
            recent_average.return_rate_pct,
            points=True,
        ),
        make_metric(
            "target",
            "Realizare target",
            MetricUnit.PERCENT,
            _ratio(current.sales, current.target),
            _ratio(previous_year.sales, previous_year.target),
            _ratio(previous_month.sales, previous_month.target),
            _ratio(recent_average.sales, recent_average.target),
            target=HUNDRED,
            points=True,
        ),
    ]


class DemoMonthlyReviewRepository(DemoInsightRepository):
    async def get_monthly_review(
        self,
        scope: AnalyticsScope,
        recent_months: int,
    ) -> MonthlyReviewResponse:
        previous_year_period = shift_month(scope.period, -12)
        previous_month_period = shift_month(scope.period, -1)
        recent_periods = [shift_month(scope.period, -offset) for offset in range(1, recent_months + 1)]
        trend_periods = [shift_month(scope.period, offset) for offset in range(-max(5, recent_months), 1)]
        seasonal_periods = [shift_month(scope.period, offset) for offset in (-25, -24, -13, -12, -1, 0)]
        periods = unique_periods([scope.period, previous_year_period, *trend_periods, *seasonal_periods])
        rng = random.Random(int.from_bytes(hashlib.sha256(scope.model_dump_json().encode()).digest()[:8], "big"))
        selected_stores = self._selected_stores(scope)
        store_entities = [
            Entity(
                store.site_code,
                store.label,
                f"{store.firm} · {store.regional} · {store.asm}",
                "store",
            )
            for store in selected_stores
        ]
        values: dict[tuple[str, str], Aggregate] = {}
        for entity in store_entities:
            base = Decimal(str(rng.uniform(32000, 105000)))
            for index, period in enumerate(periods):
                seasonal = Decimal(str(1 + 0.10 * math.sin((index + 1) / 1.7)))
                sales = _money(base * seasonal * Decimal(str(rng.uniform(0.82, 1.18))))
                receipts = Decimal(max(1, round(float(sales) / rng.uniform(115, 165))))
                units = _percent(receipts * Decimal(str(rng.uniform(1.24, 1.62))))
                gross = _money(sales / Decimal(str(rng.uniform(0.975, 0.999))))
                values[(period, entity.id)] = Aggregate(
                    sales=sales,
                    units=units,
                    receipts=receipts,
                    receipt_2plus=_percent(receipts * Decimal(str(rng.uniform(0.25, 0.43)))),
                    focus_units=_percent(units * Decimal(str(rng.uniform(0.04, 0.11)))),
                    gross_sales=gross,
                    return_value=_money(gross - sales),
                    working_days=Decimal(31),
                    target=_money(sales / Decimal(str(rng.uniform(0.84, 1.12)))),
                )
        network_groups = {"network": [entity.id for entity in store_entities]}
        network_values = aggregate_groups(values, network_groups, periods)
        current = network_values.get((scope.period, "network"), Aggregate())
        previous_year = network_values.get((previous_year_period, "network"), Aggregate())
        previous_month = network_values.get((previous_month_period, "network"), Aggregate())
        recent_average = average(
            [network_values.get((item, "network"), Aggregate()) for item in recent_periods],
            len(recent_periods),
        )

        company_groups: dict[str, list[str]] = defaultdict(list)
        manager_groups: dict[str, list[str]] = defaultdict(list)
        store_by_code = {store.site_code: store for store in selected_stores}
        for entity in store_entities:
            store = store_by_code[entity.id]
            company_groups[store.firm].append(entity.id)
            manager_groups[store.regional].append(entity.id)
        company_values = aggregate_groups(values, company_groups, periods)
        manager_values = aggregate_groups(values, manager_groups, periods)
        company_entities = [Entity(key, key, f"{len(ids)} magazine", "company") for key, ids in company_groups.items()]
        manager_entities = [Entity(key, key, f"{len(ids)} magazine", "manager") for key, ids in manager_groups.items()]

        products: list[ProductReviewRow] = []
        product_names = [
            ("Folie premium", "Cellara", "Folii Sticlă"),
            ("Folie privacy", "Cellara", "Folii Sticlă"),
            ("Husă magnetică", "Cellara", "Stil și Protecție"),
            ("Încărcător GaN", "Cellara", "Încărcare"),
            ("Cablu USB-C", "Cellara", "Încărcare"),
            ("Căști wireless", "Cellara", "Voce și Muzică"),
            ("Folie TPU Premium", "Versus", "Folii TPU"),
            ("Baterie externă", "Cellara", "Încărcare"),
            ("Suport auto", "Cellara", "Diverse"),
            ("Smart tag", "Cellara", "Diverse"),
            ("Protecție cameră", "Cellara", "Folii Sticlă"),
            ("Husă universală", "Cellara", "Stil și Protecție"),
        ]
        product_values: dict[tuple[str, str], Aggregate] = {}
        product_distributions: dict[tuple[str, str], int] = {}
        for index, (label, brand, category) in enumerate(product_names):
            product_id = f"demo-product-{index + 1}"
            base = Decimal(str(rng.uniform(8000, 120000)))
            for period in periods:
                sales = _money(base * Decimal(str(rng.uniform(0.55, 1.45))))
                units = Decimal(max(1, round(float(sales) / rng.uniform(69, 179))))
                gross = _money(sales / Decimal(str(rng.uniform(0.97, 1.0))))
                product_values[(period, product_id)] = Aggregate(
                    sales=sales,
                    units=units,
                    gross_sales=gross,
                    return_value=_money(gross - sales),
                )
                product_distributions[(period, product_id)] = rng.randint(1, max(1, len(selected_stores)))
            entity = ProductEntity(product_id, label, brand, category)
            products.append(
                product_row(
                    entity,
                    product_values[(scope.period, product_id)],
                    product_values[(previous_year_period, product_id)],
                    average(
                        [product_values[(item, product_id)] for item in recent_periods],
                        len(recent_periods),
                    ),
                    product_distributions[(scope.period, product_id)],
                    product_distributions[(previous_year_period, product_id)],
                )
            )
        products.sort(key=lambda item: item.score, reverse=True)

        category_groups: dict[str, list[str]] = defaultdict(list)
        product_entities = {item.id: item for item in products}
        for product_id, item in product_entities.items():
            category_groups[item.category].append(product_id)
        category_values = aggregate_groups(product_values, category_groups, periods)
        categories = [
            product_row(
                ProductEntity(category, category, "Portofoliu", category),
                category_values.get((scope.period, category), Aggregate()),
                category_values.get((previous_year_period, category), Aggregate()),
                average(
                    [category_values.get((item, category), Aggregate()) for item in recent_periods],
                    len(recent_periods),
                ),
                None,
                None,
            )
            for category in category_groups
        ]
        categories.sort(key=lambda item: item.sales, reverse=True)

        agent_entities = [
            Entity(
                f"{agent.site_code}:{agent.name}",
                agent.name,
                f"{agent.site_code} · {agent.regional}",
                "agent",
            )
            for agent in DEMO_AGENTS
            if agent.site_code in store_by_code
        ][:40]
        agent_values: dict[tuple[str, str], Aggregate] = {}
        for entity in agent_entities:
            for period in periods:
                store_code = entity.id.split(":", 1)[0]
                store_aggregate = values.get((period, store_code), Aggregate())
                agent_values[(period, entity.id)] = store_aggregate.divided(2)
        store_rows = build_rows(
            entities=store_entities,
            values=values,
            period=scope.period,
            previous_year_period=previous_year_period,
            previous_month_period=previous_month_period,
            recent_periods=recent_periods,
        )
        agent_rows = build_rows(
            entities=agent_entities,
            values=agent_values,
            period=scope.period,
            previous_year_period=previous_year_period,
            previous_month_period=previous_month_period,
            recent_periods=recent_periods,
        )
        returns = [
            return_row(
                entity_id=row.id,
                label=row.label,
                context=row.context,
                entity_type="store",
                current=values.get((scope.period, row.id), Aggregate()),
                previous_year=values.get((previous_year_period, row.id), Aggregate()),
                recent_average=average(
                    [values.get((item, row.id), Aggregate()) for item in recent_periods],
                    len(recent_periods),
                ),
            )
            for row in store_entities
        ]
        returns.extend(
            return_row(
                entity_id=item.id,
                label=item.label,
                context=f"{item.brand} · {item.category}",
                entity_type="product",
                current=product_values[(scope.period, item.id)],
                previous_year=product_values[(previous_year_period, item.id)],
                recent_average=average(
                    [product_values[(period, item.id)] for period in recent_periods],
                    len(recent_periods),
                ),
            )
            for item in products
        )
        returns.sort(key=lambda item: item.current_value, reverse=True)
        trend = [
            MonthlyTrendPoint(
                period=period,
                sales=_money(network_values.get((period, "network"), Aggregate()).sales),
                units=_percent(network_values.get((period, "network"), Aggregate()).units),
                receipts=_percent(network_values.get((period, "network"), Aggregate()).receipts),
                target=_money(network_values.get((period, "network"), Aggregate()).target),
                target_pct=_ratio(
                    network_values.get((period, "network"), Aggregate()).sales,
                    network_values.get((period, "network"), Aggregate()).target,
                ),
                average_receipt=network_values.get((period, "network"), Aggregate()).average_receipt,
                return_rate_pct=network_values.get((period, "network"), Aggregate()).return_rate_pct,
            )
            for period in trend_periods
        ]
        meta = OverviewMeta(
            period=scope.period,
            comparison=scope.comparison,
            as_of=None,
            is_final=True,
            data_mode=DataMode.DEMO,
            scope_label=scope_label(scope),
            generated_at=datetime.now(UTC),
            source="deterministic-demo:monthly-review",
        )
        alerts = [
            InsightAlert(
                id="demo-monthly",
                severity=AlertSeverity.INFO,
                title="Raport lunar demo",
                description="Structura, comparațiile și exporturile sunt reale; valorile sunt deterministe până la conectarea PostgreSQL.",
            ),
            *[
                InsightAlert(
                    id=f"risk-{row.id}",
                    severity=AlertSeverity.WARNING,
                    title="Entitate prioritară",
                    description=f"Scor {row.performance_score}; YoY {row.yoy_pct}% și vs media recentă {row.recent_pct}%.",
                    entity_label=row.label,
                )
                for row in store_rows
                if row.status is ReviewStatus.RISK
            ][:4],
        ]
        return MonthlyReviewResponse(
            meta=meta,
            recent_months=recent_months,
            executive=executive_metrics(current, previous_year, previous_month, recent_average),
            trend=trend,
            seasonality=seasonality_points(network_values, scope.period, len(store_entities)),
            drivers=[
                bridge(current, previous_year, "Aceeași lună anul trecut"),
                bridge(current, recent_average, f"Media ultimelor {recent_months} luni"),
            ],
            companies=build_rows(
                entities=company_entities,
                values=company_values,
                period=scope.period,
                previous_year_period=previous_year_period,
                previous_month_period=previous_month_period,
                recent_periods=recent_periods,
            ),
            managers=build_rows(
                entities=manager_entities,
                values=manager_values,
                period=scope.period,
                previous_year_period=previous_year_period,
                previous_month_period=previous_month_period,
                recent_periods=recent_periods,
            ),
            stores=store_rows,
            categories=categories,
            products=products,
            returns=returns[:60],
            agents=agent_rows,
            alerts=alerts,
            methodology=[
                "Comparația YoY folosește aceeași lună din anul precedent și cohorta organizațională curentă.",
                f"Reperul recent este media aritmetică a ultimelor {recent_months} luni complete/observate; lunile fără rezultat contribuie cu zero.",
                "Scorul combină target 40%, YoY 25%, reper recent 25% și consistență 10%.",
                "Driverii descompun exact diferența de vânzări în bonuri, produse/bon și valoare/produs.",
                "Retururile sunt raportate separat la vânzarea brută pozitivă.",
            ],
        )


class PostgresMonthlyReviewRepository(PostgresHardenedInsightRepository):
    async def get_monthly_review(self, scope: AnalyticsScope, recent_months: int) -> MonthlyReviewResponse:
        previous_year_period = shift_month(scope.period, -12)
        previous_month_period = shift_month(scope.period, -1)
        recent_periods = [shift_month(scope.period, -offset) for offset in range(1, recent_months + 1)]
        trend_periods = [shift_month(scope.period, offset) for offset in range(-max(5, recent_months), 1)]
        seasonal_periods = [shift_month(scope.period, offset) for offset in (-25, -24, -13, -12, -1, 0)]
        periods = unique_periods([scope.period, previous_year_period, *trend_periods, *seasonal_periods])
        product_periods = unique_periods([scope.period, previous_year_period, *recent_periods])
        store_records, agent_records, product_records, meta = await asyncio.gather(
            self._review_store_rows(scope, periods),
            self._review_agent_rows(scope, periods),
            self._review_product_rows(scope, product_periods),
            self._meta_for_review(scope),
        )
        store_values: dict[tuple[str, str], Aggregate] = {}
        store_entities: dict[str, Entity] = {}
        store_company: dict[str, str] = {}
        store_manager: dict[str, str] = {}
        for row in store_records:
            site_code = str(row["site_code"])
            period = str(row["import_month"])
            store_entities[site_code] = Entity(
                site_code,
                str(row["locatie"]),
                f"{row['firma']} · {row['regional']} · {row['asm']}",
                "store",
            )
            store_company[site_code] = str(row["firma"])
            store_manager[site_code] = str(row["regional"])
            store_values[(period, site_code)] = self._aggregate(row)
        company_groups: dict[str, list[str]] = defaultdict(list)
        manager_groups: dict[str, list[str]] = defaultdict(list)
        for site_code in store_entities:
            company_groups[store_company[site_code]].append(site_code)
            manager_groups[store_manager[site_code]].append(site_code)
        company_values = aggregate_groups(store_values, company_groups, periods)
        manager_values = aggregate_groups(store_values, manager_groups, periods)
        network_values = aggregate_groups(store_values, {"network": list(store_entities)}, periods)
        company_entities = [Entity(key, key, f"{len(ids)} magazine", "company") for key, ids in company_groups.items()]
        manager_entities = [Entity(key, key, f"{len(ids)} magazine", "manager") for key, ids in manager_groups.items()]
        current = network_values.get((scope.period, "network"), Aggregate())
        previous_year = network_values.get((previous_year_period, "network"), Aggregate())
        previous_month = network_values.get((previous_month_period, "network"), Aggregate())
        recent_average = average(
            [network_values.get((item, "network"), Aggregate()) for item in recent_periods],
            len(recent_periods),
        )
        stores = build_rows(
            entities=list(store_entities.values()),
            values=store_values,
            period=scope.period,
            previous_year_period=previous_year_period,
            previous_month_period=previous_month_period,
            recent_periods=recent_periods,
        )

        agent_values: dict[tuple[str, str], Aggregate] = {}
        agent_entities: dict[str, Entity] = {}
        for row in agent_records:
            identifier = f"{row['site_code']}:{row['agent']}"
            agent_entities[identifier] = Entity(
                identifier, str(row["agent"]), f"{row['locatie']} · {row['regional']}", "agent"
            )
            agent_values[(str(row["import_month"]), identifier)] = self._aggregate(row)
        agents = build_rows(
            entities=list(agent_entities.values()),
            values=agent_values,
            period=scope.period,
            previous_year_period=previous_year_period,
            previous_month_period=previous_month_period,
            recent_periods=recent_periods,
        )

        product_values: dict[tuple[str, str], Aggregate] = {}
        product_entities: dict[str, ProductEntity] = {}
        distributions: dict[tuple[str, str], int] = {}
        for row in product_records:
            identifier = str(row["item_code"])
            product_entities[identifier] = ProductEntity(
                identifier,
                str(row["item_name"]),
                str(row["brand"] or "Necunoscut"),
                str(row["category"] or "Necategorizat"),
            )
            product_values[(str(row["import_month"]), identifier)] = self._aggregate(row)
            distributions[(str(row["import_month"]), identifier)] = int(row["distribution"] or 0)
        products = [
            product_row(
                entity,
                product_values.get((scope.period, entity.id), Aggregate()),
                product_values.get((previous_year_period, entity.id), Aggregate()),
                average(
                    [product_values.get((item, entity.id), Aggregate()) for item in recent_periods],
                    len(recent_periods),
                ),
                distributions.get((scope.period, entity.id), 0),
                distributions.get((previous_year_period, entity.id), 0),
            )
            for entity in product_entities.values()
        ]
        products.sort(key=lambda item: item.score, reverse=True)
        products = products[:150]
        category_groups: dict[str, list[str]] = defaultdict(list)
        for entity in product_entities.values():
            category_groups[entity.category].append(entity.id)
        category_values = aggregate_groups(product_values, category_groups, product_periods)
        categories = [
            product_row(
                ProductEntity(category, category, "Portofoliu", category),
                category_values.get((scope.period, category), Aggregate()),
                category_values.get((previous_year_period, category), Aggregate()),
                average(
                    [category_values.get((item, category), Aggregate()) for item in recent_periods],
                    len(recent_periods),
                ),
                None,
                None,
            )
            for category in category_groups
        ]
        categories.sort(key=lambda item: item.sales, reverse=True)

        returns = [
            return_row(
                entity_id=entity.id,
                label=entity.label,
                context=entity.context,
                entity_type="store",
                current=store_values.get((scope.period, entity.id), Aggregate()),
                previous_year=store_values.get((previous_year_period, entity.id), Aggregate()),
                recent_average=average(
                    [store_values.get((item, entity.id), Aggregate()) for item in recent_periods],
                    len(recent_periods),
                ),
            )
            for entity in store_entities.values()
        ]
        returns.extend(
            return_row(
                entity_id=entity.id,
                label=entity.label,
                context=f"{entity.brand} · {entity.category}",
                entity_type="product",
                current=product_values.get((scope.period, entity.id), Aggregate()),
                previous_year=product_values.get((previous_year_period, entity.id), Aggregate()),
                recent_average=average(
                    [product_values.get((item, entity.id), Aggregate()) for item in recent_periods],
                    len(recent_periods),
                ),
            )
            for entity in product_entities.values()
        )
        returns.extend(
            return_row(
                entity_id=entity.id,
                label=entity.label,
                context=entity.context,
                entity_type="agent",
                current=agent_values.get((scope.period, entity.id), Aggregate()),
                previous_year=agent_values.get((previous_year_period, entity.id), Aggregate()),
                recent_average=average(
                    [agent_values.get((item, entity.id), Aggregate()) for item in recent_periods],
                    len(recent_periods),
                ),
            )
            for entity in agent_entities.values()
        )
        returns = sorted(returns, key=lambda item: item.current_value, reverse=True)[:100]
        trend = [
            self._trend_point(period, network_values.get((period, "network"), Aggregate())) for period in trend_periods
        ]
        alerts = self._review_alerts(meta, stores, products, returns, recent_months)
        return MonthlyReviewResponse(
            meta=meta,
            recent_months=recent_months,
            executive=executive_metrics(current, previous_year, previous_month, recent_average),
            trend=trend,
            seasonality=seasonality_points(network_values, scope.period, len(store_entities)),
            drivers=[
                bridge(current, previous_year, "Aceeași lună anul trecut"),
                bridge(current, recent_average, f"Media ultimelor {recent_months} luni"),
            ],
            companies=build_rows(
                entities=company_entities,
                values=company_values,
                period=scope.period,
                previous_year_period=previous_year_period,
                previous_month_period=previous_month_period,
                recent_periods=recent_periods,
            ),
            managers=build_rows(
                entities=manager_entities,
                values=manager_values,
                period=scope.period,
                previous_year_period=previous_year_period,
                previous_month_period=previous_month_period,
                recent_periods=recent_periods,
            ),
            stores=stores,
            categories=categories,
            products=products,
            returns=returns,
            agents=agents,
            alerts=alerts,
            methodology=[
                "Cohorta este formată din magazinele active și filtrele organizaționale curente; selecția explicită de magazine domină filtrele părinte.",
                f"YoY compară {scope.period} cu {previous_year_period}; reperul recent este media lunilor {', '.join(recent_periods)}.",
                "Magazinele sau produsele fără rezultat într-o lună recentă contribuie cu zero, astfel încât pierderea distribuției nu este ascunsă.",
                "Scorul de performanță: target 40%, YoY 25%, reper recent 25%, consistență 10%.",
                "Driver bridge: bonuri + produse/bon + valoare/produs = diferența exactă de vânzări.",
                "Vânzările și unitățile sunt nete de retururi; rata retur = valoare retur / vânzare brută pozitivă.",
                "Exportul Excel păstrează numerele ca valori numerice și separă fiecare nivel într-o foaie dedicată.",
            ],
        )

    async def _meta_for_review(self, scope: AnalyticsScope) -> OverviewMeta:
        summary = await self._fetch_summary(scope, scope.period)
        return OverviewMeta(
            period=scope.period,
            comparison=scope.comparison,
            as_of=summary["last_sale_date"],
            is_final=bool(summary["is_month_final"]),
            data_mode=DataMode.POSTGRES,
            scope_label=scope_label(scope),
            generated_at=datetime.now(UTC),
            source="sales_transactions/reporting targets",
        )

    @staticmethod
    def _aggregate(row: Any) -> Aggregate:
        return Aggregate(
            sales=_money(row.get("sales", row.get("net_sales", 0))),
            units=_percent(row.get("units", row.get("net_units", 0))),
            receipts=_percent(row.get("receipts", 0)),
            receipt_2plus=_percent(row.get("receipt_2plus", 0)),
            focus_units=_percent(row.get("focus_units", 0)),
            gross_sales=_money(row.get("gross_sales", 0)),
            return_value=_money(row.get("return_value", 0)),
            working_days=_percent(row.get("working_days", 0)),
            target=_money(row.get("target", 0)),
        )

    @staticmethod
    def _trend_point(period: str, value: Aggregate) -> MonthlyTrendPoint:
        return MonthlyTrendPoint(
            period=period,
            sales=_money(value.sales),
            units=_percent(value.units),
            receipts=_percent(value.receipts),
            target=_money(value.target),
            target_pct=_ratio(value.sales, value.target),
            average_receipt=value.average_receipt,
            return_rate_pct=value.return_rate_pct,
        )

    @staticmethod
    def _scope_clauses(scope: AnalyticsScope, params: list[Any], alias: str = "store") -> list[str]:
        clauses = [f"{alias}.locatie NOT ILIKE 'TR %'"]
        if scope.stores:
            params.append(list(scope.stores))
            clauses.append(f"{alias}.site_code = ANY(${len(params)}::text[])")
        else:
            clauses.append(f"{alias}.is_active = TRUE")
            for column, value in (
                ("firma", scope.firm),
                ("asm", scope.asm),
            ):
                if value:
                    params.append(value)
                    clauses.append(f"{alias}.{column} = ${len(params)}")
            if scope.regional:
                params.append(list(scope.regional))
                clauses.append(f"{alias}.regional = ANY(${len(params)}::text[])")
        return clauses

    async def _review_store_rows(self, scope: AnalyticsScope, periods: Sequence[str]) -> Sequence[asyncpg.Record]:
        params: list[Any] = [list(periods), list(scope.agent) or None]
        clauses = self._scope_clauses(scope, params)
        where_scope = " AND ".join(clauses)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH eligible AS MATERIALIZED (
                    SELECT store.site_code, store.locatie, store.firma, store.regional, store.asm
                    FROM stores store WHERE {where_scope}
                ), requested AS (SELECT UNNEST($1::text[]) AS import_month),
                tx AS (
                    SELECT sale.import_month, sale.site_code,
                           SUM(sale.total_value) AS sales,
                           SUM(sale.quantity) AS units,
                           SUM(CASE WHEN NOT sale.is_return THEN sale.total_value ELSE 0 END) AS gross_sales,
                           SUM(CASE WHEN sale.is_return THEN ABS(sale.total_value) ELSE 0 END) AS return_value,
                           SUM(CASE WHEN focus.item_code IS NOT NULL AND NOT sale.is_return THEN GREATEST(sale.quantity, 0) ELSE 0 END) AS focus_units,
                           COUNT(DISTINCT sale.sale_date) FILTER (WHERE NOT sale.is_return) AS working_days
                    FROM sales_transactions sale
                    JOIN eligible ON eligible.site_code = sale.site_code
                    LEFT JOIN focus_products focus ON focus.item_code = sale.item_code
                    WHERE sale.import_month = ANY($1::text[]) AND NOT sale.is_cartela
                      AND ($2::text[] IS NULL OR sale.agent = ANY($2::text[]))
                    GROUP BY sale.import_month, sale.site_code
                ), receipts AS (
                    SELECT receipt.import_month, receipt.site_code,
                           COUNT(*) FILTER (WHERE receipt.positive_units > 0) AS receipts,
                           COUNT(*) FILTER (WHERE receipt.positive_units >= 2) AS receipt_2plus
                    FROM (
                        SELECT sale.import_month, sale.site_code, sale.sale_date, sale.bon_nr,
                               SUM(CASE WHEN NOT sale.is_return THEN GREATEST(sale.quantity, 0) ELSE 0 END) AS positive_units
                        FROM sales_transactions sale
                        JOIN eligible ON eligible.site_code = sale.site_code
                        WHERE sale.import_month = ANY($1::text[]) AND NOT sale.is_cartela
                          AND ($2::text[] IS NULL OR sale.agent = ANY($2::text[]))
                        GROUP BY sale.import_month, sale.site_code, sale.sale_date, sale.bon_nr
                    ) receipt
                    GROUP BY receipt.import_month, receipt.site_code
                ), agent_target AS (
                    SELECT target.import_month, target.site_code,
                           SUM(target.target_value) AS target_value
                    FROM agent_targets target
                    WHERE target.import_month = ANY($1::text[])
                      AND ($2::text[] IS NULL OR target.agent = ANY($2::text[]))
                    GROUP BY target.import_month, target.site_code
                )
                SELECT requested.import_month, eligible.*,
                       COALESCE(tx.sales, 0) AS sales,
                       COALESCE(tx.units, 0) AS units,
                       COALESCE(tx.gross_sales, 0) AS gross_sales,
                       COALESCE(tx.return_value, 0) AS return_value,
                       COALESCE(tx.focus_units, 0) AS focus_units,
                       COALESCE(tx.working_days, 0) AS working_days,
                       COALESCE(receipts.receipts, 0) AS receipts,
                       COALESCE(receipts.receipt_2plus, 0) AS receipt_2plus,
                       COALESCE(CASE WHEN $2::text[] IS NULL THEN store_target.target_value ELSE agent_target.target_value END, 0) AS target
                FROM eligible CROSS JOIN requested
                LEFT JOIN tx USING (import_month, site_code)
                LEFT JOIN receipts USING (import_month, site_code)
                LEFT JOIN store_targets store_target ON store_target.import_month = requested.import_month AND store_target.site_code = eligible.site_code
                LEFT JOIN agent_target ON agent_target.import_month = requested.import_month AND agent_target.site_code = eligible.site_code
                ORDER BY requested.import_month, eligible.site_code
            """,
                *params,
            )

    async def _review_agent_rows(self, scope: AnalyticsScope, periods: Sequence[str]) -> Sequence[asyncpg.Record]:
        params: list[Any] = [list(periods)]
        clauses = self._scope_clauses(scope, params)
        if scope.agent:
            params.append(list(scope.agent))
            clauses.append(f"sale.agent = ANY(${len(params)}::text[])")
        where_scope = " AND ".join(clauses)
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                WITH base AS (
                    SELECT sale.import_month, sale.site_code, sale.agent,
                           MAX(store.locatie) AS locatie, MAX(store.firma) AS firma,
                           MAX(store.regional) AS regional, MAX(store.asm) AS asm,
                           SUM(sale.total_value) AS sales, SUM(sale.quantity) AS units,
                           SUM(CASE WHEN NOT sale.is_return THEN sale.total_value ELSE 0 END) AS gross_sales,
                           SUM(CASE WHEN sale.is_return THEN ABS(sale.total_value) ELSE 0 END) AS return_value,
                           SUM(CASE WHEN focus.item_code IS NOT NULL AND NOT sale.is_return THEN GREATEST(sale.quantity, 0) ELSE 0 END) AS focus_units,
                           COUNT(DISTINCT sale.sale_date) FILTER (WHERE NOT sale.is_return) AS working_days
                    FROM sales_transactions sale
                    JOIN stores store ON store.site_code = sale.site_code
                    LEFT JOIN focus_products focus ON focus.item_code = sale.item_code
                    WHERE sale.import_month = ANY($1::text[]) AND NOT sale.is_cartela AND {where_scope}
                    GROUP BY sale.import_month, sale.site_code, sale.agent
                ), receipt_detail AS (
                    SELECT sale.import_month, sale.site_code, sale.agent,
                           sale.sale_date, sale.bon_nr,
                           SUM(CASE WHEN NOT sale.is_return THEN GREATEST(sale.quantity, 0) ELSE 0 END) AS positive_units
                    FROM sales_transactions sale
                    JOIN stores store ON store.site_code = sale.site_code
                    WHERE sale.import_month = ANY($1::text[])
                      AND NOT sale.is_cartela AND {where_scope}
                    GROUP BY sale.import_month, sale.site_code, sale.agent,
                             sale.sale_date, sale.bon_nr
                ), receipts AS (
                    SELECT import_month, site_code, agent,
                           COUNT(*) FILTER (WHERE positive_units > 0) AS receipts,
                           COUNT(*) FILTER (WHERE positive_units >= 2) AS receipt_2plus
                    FROM receipt_detail
                    GROUP BY import_month, site_code, agent
                )
                SELECT base.*, COALESCE(receipts.receipts, 0) AS receipts,
                       COALESCE(receipts.receipt_2plus, 0) AS receipt_2plus,
                       COALESCE(target.target_value, 0) AS target
                FROM base
                LEFT JOIN receipts USING (import_month, site_code, agent)
                LEFT JOIN agent_targets target USING (import_month, site_code, agent)
                ORDER BY base.import_month, base.site_code, base.agent
            """,
                *params,
            )

    async def _review_product_rows(self, scope: AnalyticsScope, periods: Sequence[str]) -> Sequence[asyncpg.Record]:
        params: list[Any] = [list(periods)]
        clauses = self._scope_clauses(scope, params)
        if scope.agent:
            params.append(list(scope.agent))
            clauses.append(f"sale.agent = ANY(${len(params)}::text[])")
        async with self.pool.acquire() as connection:
            return await connection.fetch(
                f"""
                SELECT sale.import_month, sale.item_code,
                       MAX(sale.item_name) AS item_name,
                       MAX(COALESCE(sale.brand, 'Necunoscut')) AS brand,
                       MAX(COALESCE(sale.category, 'Necategorizat')) AS category,
                       SUM(sale.total_value) AS sales,
                       SUM(sale.quantity) AS units,
                       SUM(CASE WHEN NOT sale.is_return THEN sale.total_value ELSE 0 END) AS gross_sales,
                       SUM(CASE WHEN sale.is_return THEN ABS(sale.total_value) ELSE 0 END) AS return_value,
                       COUNT(DISTINCT sale.site_code) FILTER (WHERE NOT sale.is_return AND sale.quantity > 0) AS distribution,
                       0 AS receipts, 0 AS receipt_2plus, 0 AS focus_units, 0 AS working_days, 0 AS target
                FROM sales_transactions sale
                JOIN stores store ON store.site_code = sale.site_code
                WHERE sale.import_month = ANY($1::text[]) AND NOT sale.is_cartela
                  AND {" AND ".join(clauses)}
                GROUP BY sale.import_month, sale.item_code
                ORDER BY sale.import_month, ABS(SUM(sale.total_value)) DESC
            """,
                *params,
            )

    @staticmethod
    def _review_alerts(
        meta: OverviewMeta,
        stores: Sequence[PerformanceReviewRow],
        products: Sequence[ProductReviewRow],
        returns: Sequence[ReturnReviewRow],
        recent_months: int,
    ) -> list[InsightAlert]:
        alerts: list[InsightAlert] = []
        if not meta.is_final:
            alerts.append(
                InsightAlert(
                    id="monthly-open",
                    severity=AlertSeverity.WARNING,
                    title="Lună încă deschisă",
                    description="Raportul este disponibil, dar rezultatele și comparațiile se vor modifica până la închiderea lunii.",
                )
            )
        risks = [row for row in stores if row.status is ReviewStatus.RISK]
        if risks:
            alerts.append(
                InsightAlert(
                    id="monthly-risk-stores",
                    severity=AlertSeverity.CRITICAL,
                    title="Magazine cu risc simultan",
                    description=f"{len(risks)} magazine sunt sub prag la target, YoY și media ultimelor {recent_months} luni.",
                )
            )
        slowing = [row for row in stores if row.status is ReviewStatus.SLOWING]
        if slowing:
            alerts.append(
                InsightAlert(
                    id="monthly-slowing",
                    severity=AlertSeverity.WARNING,
                    title="Creștere anuală, încetinire recentă",
                    description=f"{len(slowing)} magazine sunt încă pozitive YoY, dar au coborât sub reperul recent.",
                )
            )
        product_risks = [row for row in products if row.status in {ReviewStatus.RISK, ReviewStatus.EXITED}]
        if product_risks:
            alerts.append(
                InsightAlert(
                    id="monthly-product-risk",
                    severity=AlertSeverity.WARNING,
                    title="Produse cu pierdere de tracțiune",
                    description=f"{len(product_risks)} produse din topul de impact au scădere simultană sau au ieșit din vânzare.",
                )
            )
        return_risks = [row for row in returns if row.status is ReviewStatus.RISK]
        if return_risks:
            alerts.append(
                InsightAlert(
                    id="monthly-return-risk",
                    severity=AlertSeverity.WARNING,
                    title="Retururi peste reper",
                    description=f"{len(return_risks)} entități depășesc semnificativ rata istorică/recentă de retur.",
                )
            )
        if not alerts:
            alerts.append(
                InsightAlert(
                    id="monthly-healthy",
                    severity=AlertSeverity.INFO,
                    title="Fără abateri critice",
                    description="Nu au fost detectate combinații critice în regulile actuale de management al performanței.",
                )
            )
        return alerts[:8]
