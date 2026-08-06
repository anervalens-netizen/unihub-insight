from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from unihub_insight_api.domain import ModuleAnalyticsResponse, ModuleId
from unihub_insight_api.services.metric_catalog import METRIC_CATALOG, MODULE_PRIMARY_METRIC_IDS

METRICS_BY_ID = {metric.id: metric for metric in METRIC_CATALOG}


@dataclass(frozen=True)
class ModuleWindow:
    start: str | None = None
    end: str | None = None
    requested_comparisons: tuple[str, ...] = ()
    ignored_comparisons: tuple[str, ...] = ()


def allowed_module_window(module: ModuleId, window: ModuleWindow) -> ModuleWindow:
    metric = METRICS_BY_ID[MODULE_PRIMARY_METRIC_IDS[module]]
    return ModuleWindow(
        start=window.start,
        end=window.end,
        requested_comparisons=tuple(
            comparison for comparison in window.requested_comparisons if comparison in metric.allowed_comparisons
        ),
        ignored_comparisons=tuple(
            comparison for comparison in window.requested_comparisons if comparison not in metric.allowed_comparisons
        ),
    )


def apply_module_window(
    data: ModuleAnalyticsResponse,
    window: ModuleWindow,
    comparison_data: dict[str, ModuleAnalyticsResponse] | None = None,
) -> ModuleAnalyticsResponse:
    temporal_points = {
        comparison: {point.key: point for point in response.trend}
        for comparison, response in (comparison_data or {}).items()
    }
    primary_values = [point.primary for point in data.trend]
    enriched_trend = []
    for index, point in enumerate(data.trend):
        comparisons = dict(point.comparisons)
        for comparison, points in temporal_points.items():
            reference = points.get(point.key)
            comparisons[comparison] = reference.comparison if reference else None
        if "recent-average" in window.requested_comparisons:
            values = [value for value in primary_values[max(0, index - 3) : index] if value is not None]
            comparisons["recent-average"] = sum(values, Decimal(0)) / Decimal(len(values)) if values else None
        if "forecast" in window.requested_comparisons and data.module is ModuleId.PLANNING:
            comparisons["forecast"] = point.primary
        enriched_trend.append(point.model_copy(update={"comparisons": comparisons}))

    if window.start is None or window.end is None:
        trend = enriched_trend
        matrix = data.matrix
    else:
        trend = [point for point in enriched_trend if window.start <= point.key <= window.end]
        matrix = [cell for cell in data.matrix if window.start <= cell.x <= window.end]

    available = {"target"}
    available.update(temporal_points)
    if "recent-average" in window.requested_comparisons:
        available.add("recent-average")
    if data.module is ModuleId.PLANNING:
        available.add("forecast")
    missing = sorted(set(window.requested_comparisons) - available)
    warnings = list(data.meta.warnings)
    if window.ignored_comparisons:
        warnings.append(
            "Comparații ignorate de allowlist-ul metricii native: " + ", ".join(window.ignored_comparisons) + "."
        )
    if missing:
        warnings.append("Comparații indisponibile în contractul nativ curent: " + ", ".join(missing) + ".")

    return data.model_copy(
        update={
            "meta": data.meta.model_copy(
                update={
                    "range_start": window.start,
                    "range_end": window.end,
                    "requested_comparisons": window.requested_comparisons,
                    "warnings": tuple(warnings),
                }
            ),
            "trend": trend,
            "matrix": matrix,
        }
    )
