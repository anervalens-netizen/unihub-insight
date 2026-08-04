from unihub_insight_api.domain import MetricDefinition, MetricUnit


METRIC_CATALOG: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        id="sales.total",
        display_name="Vânzări",
        description="Suma vânzărilor nete de accesorii în scope.",
        unit=MetricUnit.CURRENCY,
        aggregation="sum",
        allowed_dimensions=("firm", "regional", "asm", "store", "agent", "time"),
        allowed_grains=("day", "month", "year"),
        comparison_policy="previous-period-or-year",
        missing_policy="covered-empty-is-zero",
    ),
    MetricDefinition(
        id="target.progress_pct",
        display_name="Realizare target",
        description="Vânzări împărțite la target, exprimat în puncte procentuale.",
        unit=MetricUnit.PERCENT,
        aggregation="ratio-of-sums",
        allowed_dimensions=("firm", "regional", "asm", "store", "agent", "time"),
        allowed_grains=("month", "year"),
        comparison_policy="previous-period-or-year",
        missing_policy="null-when-target-non-positive",
    ),
    MetricDefinition(
        id="forecast.linear",
        display_name="Forecast run-rate",
        description="Proiecție liniară explicită pe baza ritmului până la cutoff.",
        unit=MetricUnit.CURRENCY,
        aggregation="derived",
        allowed_dimensions=("firm", "regional", "asm", "store", "agent"),
        allowed_grains=("month",),
        comparison_policy="target",
        missing_policy="null-without-cutoff",
    ),
    MetricDefinition(
        id="receipt_2plus_pct",
        display_name="Bonuri cu 2+ accesorii",
        description="Ponderea bonurilor canonice cu cel puțin două accesorii.",
        unit=MetricUnit.PERCENT,
        aggregation="ratio-of-sums",
        allowed_dimensions=("firm", "regional", "asm", "store", "agent", "time"),
        allowed_grains=("day", "month", "year"),
        comparison_policy="previous-period-or-year",
        missing_policy="null-when-no-receipts",
    ),
)
