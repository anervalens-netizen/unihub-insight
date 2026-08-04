from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, HTTPException, Query, Request, status

from unihub_insight_api.config import Settings
from unihub_insight_api.domain import AnalyticsScope, ComparisonMode
from unihub_insight_api.repositories import AnalyticsRepository, DemoAnalyticsRepository


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


async def get_repository(request: Request) -> AnalyticsRepository:
    settings = cast(Settings, request.app.state.settings)
    if settings.data_mode == "demo":
        return DemoAnalyticsRepository()

    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL analytics pool is unavailable.",
        )

    from unihub_insight_api.repositories.postgres import PostgresAnalyticsRepository

    return cast(AnalyticsRepository, PostgresAnalyticsRepository(pool))


RepositoryDependency = Annotated[AnalyticsRepository, Depends(get_repository)]
ScopeDependency = Annotated[AnalyticsScope, Depends(analytics_scope)]
