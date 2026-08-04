from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from unihub_insight_api.api.dependencies import RepositoryDependency, ScopeDependency
from unihub_insight_api.domain import FilterOptionsResponse, MetricDefinition, OverviewResponse
from unihub_insight_api.services import METRIC_CATALOG


router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/filters/options", response_model=FilterOptionsResponse)
async def filter_options(
    repository: RepositoryDependency,
    period: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
) -> FilterOptionsResponse:
    return await repository.get_filter_options(period)


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    repository: RepositoryDependency,
    scope: ScopeDependency,
) -> OverviewResponse:
    return await repository.get_overview(scope)


@router.get("/catalog/metrics", response_model=list[MetricDefinition])
async def metric_catalog() -> list[MetricDefinition]:
    return list(METRIC_CATALOG)
