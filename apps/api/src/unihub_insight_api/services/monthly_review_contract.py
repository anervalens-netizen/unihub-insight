from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from unihub_insight_api.domain import MetricDefinition, MetricUnit


@dataclass(frozen=True)
class MonthlyReviewScoringContract:
    version: int
    target_weight: Decimal
    yoy_weight: Decimal
    recent_weight: Decimal
    consistency_weight: Decimal
    risk_target_threshold: Decimal
    watch_target_threshold: Decimal
    outperforming_target_threshold: Decimal
    volatility_threshold: Decimal
    meaningful_recent_delta: Decimal
    meaningful_yoy_delta: Decimal

    @property
    def total_weight(self) -> Decimal:
        return self.target_weight + self.yoy_weight + self.recent_weight + self.consistency_weight


MONTHLY_REVIEW_SCORING = MonthlyReviewScoringContract(
    version=1,
    target_weight=Decimal("0.40"),
    yoy_weight=Decimal("0.25"),
    recent_weight=Decimal("0.25"),
    consistency_weight=Decimal("0.10"),
    risk_target_threshold=Decimal("85"),
    watch_target_threshold=Decimal("95"),
    outperforming_target_threshold=Decimal("100"),
    volatility_threshold=Decimal("65"),
    meaningful_recent_delta=Decimal("5"),
    meaningful_yoy_delta=Decimal("5"),
)

MONTHLY_REVIEW_DRIVER_FORMULA = (
    "sales_difference = receipts_effect + units_per_receipt_effect + value_per_unit_and_mix_effect"
)


def _review_metric(
    metric_id: str,
    name: str,
    description: str,
    unit: MetricUnit,
    *,
    aggregation: str,
    missing: str,
) -> MetricDefinition:
    return MetricDefinition(
        id=metric_id,
        version=1,
        display_name=name,
        description=description,
        unit=unit,
        aggregation=aggregation,
        allowed_dimensions=("firm", "regional", "asm", "store", "agent", "time"),
        allowed_grains=("month",),
        comparison_policy="same-month-previous-year,previous-month,trailing-average",
        missing_policy=missing,
        formula_reference=f"unihub-insight:monthly-review:{metric_id}:v1",
    )


MONTHLY_REVIEW_METRICS: tuple[MetricDefinition, ...] = (
    _review_metric(
        "sales",
        "Vânzări lunare",
        "Vânzări nete în Monthly Performance Review.",
        MetricUnit.CURRENCY,
        aggregation="sum",
        missing="covered-empty-is-zero",
    ),
    _review_metric(
        "units",
        "Unități lunare",
        "Cantitatea netă de accesorii.",
        MetricUnit.INTEGER,
        aggregation="sum",
        missing="covered-empty-is-zero",
    ),
    _review_metric(
        "receipts",
        "Bonuri lunare",
        "Numărul canonic de bonuri pozitive.",
        MetricUnit.INTEGER,
        aggregation="sum",
        missing="covered-empty-is-zero",
    ),
    _review_metric(
        "average_receipt",
        "Valoare medie bon",
        "Vânzări nete împărțite la numărul de bonuri.",
        MetricUnit.CURRENCY,
        aggregation="ratio-of-sums",
        missing="null-when-no-receipts",
    ),
    _review_metric(
        "units_per_receipt",
        "Produse per bon",
        "Cantitate netă împărțită la numărul de bonuri.",
        MetricUnit.DECIMAL,
        aggregation="ratio-of-sums",
        missing="null-when-no-receipts",
    ),
    _review_metric(
        "value_per_unit",
        "Valoare per produs",
        "Vânzări nete împărțite la cantitatea netă.",
        MetricUnit.CURRENCY,
        aggregation="ratio-of-sums",
        missing="null-when-no-positive-net-units",
    ),
    _review_metric(
        "bon2acc",
        "Bonuri cu 2+ accesorii",
        "Bonuri cu minimum două accesorii împărțite la toate bonurile.",
        MetricUnit.PERCENT,
        aggregation="ratio-of-sums",
        missing="null-when-no-receipts",
    ),
    _review_metric(
        "focus",
        "Pondere Focus",
        "Cantitatea produselor Focus împărțită la cantitatea netă.",
        MetricUnit.PERCENT,
        aggregation="ratio-of-sums",
        missing="null-when-no-positive-net-units",
    ),
    _review_metric(
        "returns",
        "Rată retur",
        "Valoarea absolută a retururilor împărțită la vânzarea brută pozitivă.",
        MetricUnit.PERCENT,
        aggregation="ratio-of-sums",
        missing="null-when-no-positive-gross-sales",
    ),
    _review_metric(
        "target",
        "Realizare target",
        "Vânzări nete împărțite la targetul canonic al scope-ului.",
        MetricUnit.PERCENT,
        aggregation="ratio-of-sums",
        missing="null-when-target-non-positive",
    ),
)

MONTHLY_REVIEW_METRIC_IDS = frozenset(metric.id for metric in MONTHLY_REVIEW_METRICS)
