from __future__ import annotations

from typing import Annotated, Literal, cast

from fastapi import Depends, HTTPException, Query, Request, status

from unihub_insight_api.auth import get_current_user, require_capability
from unihub_insight_api.config import Settings
from unihub_insight_api.domain import AnalyticsScope, Capability, ComparisonMode, UserContext
from unihub_insight_api.repositories import AnalyticsRepository, DemoAnalyticsRepository
from unihub_insight_api.repositories.dashboards import DashboardStore
from unihub_insight_api.services.module_window import ModuleWindow

ALLOWED_COMPARISONS = frozenset({"target", "forecast", "previous-period", "previous-year", "recent-average"})


def parse_stores(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for item in value.split(","):
        normalized = item.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


async def analytics_scope(
    period: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    comparison: Annotated[ComparisonMode, Query()] = ComparisonMode.PREVIOUS_YEAR,
    firm: Annotated[str | None, Query(max_length=120)] = None,
    regional: Annotated[str | None, Query(max_length=120)] = None,
    asm: Annotated[str | None, Query(max_length=120)] = None,
    stores: Annotated[str | None, Query(max_length=2000)] = None,
    agent: Annotated[str | None, Query(max_length=180)] = None,
) -> AnalyticsScope:
    return AnalyticsScope(
        period=period,
        comparison=comparison,
        firm=firm or None,
        regional=regional or None,
        asm=asm or None,
        stores=parse_stores(stores),
        agent=agent or None,
    )


def _shift_month(period: str, offset: int) -> str:
    year, month = (int(part) for part in period.split("-"))
    absolute = year * 12 + month - 1 + offset
    next_year, zero_month = divmod(absolute, 12)
    return f"{next_year:04d}-{zero_month + 1:02d}"


async def module_window(
    period: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    range_preset: Annotated[
        Literal["month", "ytd", "3", "6", "12", "year", "custom"] | None,
        Query(alias="range"),
    ] = None,
    start: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
    end: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None,
    comparisons: Annotated[str | None, Query(max_length=240)] = None,
) -> ModuleWindow:
    requested = tuple(dict.fromkeys(item.strip() for item in (comparisons or "").split(",") if item.strip()))
    unknown = set(requested) - ALLOWED_COMPARISONS
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Comparații neacceptate: {', '.join(sorted(unknown))}.",
        )
    if range_preset is None:
        return ModuleWindow(requested_comparisons=requested)
    resolved_end = end if range_preset == "custom" and end else period
    if resolved_end != period:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Capătul intervalului trebuie să coincidă cu perioada analitică.",
        )
    if range_preset in {"ytd", "year"}:
        resolved_start = f"{period[:4]}-01"
    elif range_preset in {"3", "6", "12"}:
        resolved_start = _shift_month(period, -(int(range_preset) - 1))
    elif range_preset == "custom":
        resolved_start = start or resolved_end
    else:
        resolved_start = period
    if resolved_start > resolved_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Începutul intervalului nu poate fi după sfârșit.",
        )
    return ModuleWindow(
        start=resolved_start,
        end=resolved_end,
        requested_comparisons=requested,
    )


async def get_repository(request: Request) -> AnalyticsRepository:
    repository = getattr(request.app.state, "analytics_repository", None)
    if repository is not None:
        return cast(AnalyticsRepository, repository)

    settings = cast(Settings, request.app.state.settings)
    if settings.data_mode == "demo":
        repository = DemoAnalyticsRepository()
        request.app.state.analytics_repository = repository
        return cast(AnalyticsRepository, repository)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Analytics repository is unavailable.",
    )


async def get_dashboard_store(request: Request) -> DashboardStore:
    store = getattr(request.app.state, "dashboard_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard metadata store is unavailable.",
        )
    return cast(DashboardStore, store)


RepositoryDependency = Annotated[AnalyticsRepository, Depends(get_repository)]
DashboardStoreDependency = Annotated[DashboardStore, Depends(get_dashboard_store)]
ScopeDependency = Annotated[AnalyticsScope, Depends(analytics_scope)]
ModuleWindowDependency = Annotated[ModuleWindow, Depends(module_window)]
UserDependency = Annotated[UserContext, Depends(get_current_user)]
AnalyticsUserDependency = Annotated[
    UserContext,
    Depends(require_capability(Capability.ANALYTICS)),
]
