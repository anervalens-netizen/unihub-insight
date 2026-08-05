from __future__ import annotations

from dataclasses import dataclass

from unihub_insight_api.domain import ComparisonMode, ModuleAnalyticsResponse, ModuleId


@dataclass(frozen=True)
class ModuleWindow:
    start: str | None = None
    end: str | None = None
    requested_comparisons: tuple[str, ...] = ()


def apply_module_window(data: ModuleAnalyticsResponse, window: ModuleWindow) -> ModuleAnalyticsResponse:
    if window.start is None or window.end is None:
        trend = data.trend
        matrix = data.matrix
    else:
        trend = [point for point in data.trend if window.start <= point.key <= window.end]
        matrix = [cell for cell in data.matrix if window.start <= cell.x <= window.end]

    available = {"target"}
    if data.meta.comparison is ComparisonMode.PREVIOUS_MONTH:
        available.add("previous-period")
    elif data.meta.comparison is ComparisonMode.PREVIOUS_YEAR:
        available.add("previous-year")
    if data.module is ModuleId.PLANNING:
        available.add("forecast")
    missing = sorted(set(window.requested_comparisons) - available)
    warnings = list(data.meta.warnings)
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
