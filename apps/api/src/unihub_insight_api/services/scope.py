from __future__ import annotations

import calendar
from datetime import date

from unihub_insight_api.domain import AnalyticsScope, ComparisonMode


def previous_period(period: str, comparison: ComparisonMode) -> str | None:
    year, month = (int(part) for part in period.split("-"))
    if comparison is ComparisonMode.NONE:
        return None
    if comparison is ComparisonMode.PREVIOUS_YEAR:
        return f"{year - 1:04d}-{month:02d}"
    if month == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month - 1:02d}"


def scope_label(scope: AnalyticsScope) -> str:
    segments: list[str] = []
    if scope.stores:
        segments.append(f"Magazin {scope.stores[0]}" if len(scope.stores) == 1 else f"{len(scope.stores)} magazine")
    else:
        if scope.firm:
            segments.append(scope.firm)
        if scope.regional:
            segments.append(scope.regional)
        if scope.asm:
            segments.append(scope.asm)
    if scope.agent:
        segments.append(scope.agent)
    return " · ".join(segments) if segments else "Toată rețeaua"


def period_last_day(period: str) -> date:
    year, month = (int(part) for part in period.split("-"))
    return date(year, month, calendar.monthrange(year, month)[1])
