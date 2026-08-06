from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from unihub_insight_api.api.dependencies import ModuleWindowDependency, RepositoryDependency, ScopeDependency
from unihub_insight_api.auth import require_capability
from unihub_insight_api.domain import (
    AnalyticsCatalogResponse,
    Capability,
    ComparisonMode,
    FilterOptionsResponse,
    MetricDefinition,
    ModuleAnalyticsResponse,
    ModuleId,
    OverviewResponse,
    UserContext,
)
from unihub_insight_api.services import ANALYTICS_CATALOG, METRIC_CATALOG
from unihub_insight_api.services.module_availability import (
    unavailable_module_response,
    unavailable_source_domains,
)
from unihub_insight_api.services.module_window import apply_module_window

router = APIRouter(prefix="/api/v1", tags=["analytics"])

MODULE_CAPABILITIES: dict[ModuleId, Capability] = {
    ModuleId.SALES: Capability.ANALYTICS,
    ModuleId.PERFORMANCE: Capability.ANALYTICS,
    ModuleId.CAMPAIGNS: Capability.ANALYTICS,
    ModuleId.WORKFORCE: Capability.MANAGEMENT,
    ModuleId.COMPENSATION: Capability.HR,
    ModuleId.FINANCE: Capability.PNL,
    ModuleId.PLANNING: Capability.MANAGEMENT,
}


@router.get("/filters/options", response_model=FilterOptionsResponse)
async def filter_options(
    repository: RepositoryDependency,
    period: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    _user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
) -> FilterOptionsResponse:
    return await repository.get_filter_options(period)


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    repository: RepositoryDependency,
    scope: ScopeDependency,
    _user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
) -> OverviewResponse:
    return await repository.get_overview(scope)


@router.get("/modules/{module}", response_model=ModuleAnalyticsResponse)
async def module_analytics(
    module: ModuleId,
    repository: RepositoryDependency,
    scope: ScopeDependency,
    window: ModuleWindowDependency,
    user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
) -> ModuleAnalyticsResponse:
    required = MODULE_CAPABILITIES[module]
    if required not in user.capabilities:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Capability {required.value} is required.",
        )
    compensation_differentiating_scope = module is ModuleId.COMPENSATION and (
        scope.regional or scope.asm or scope.stores or scope.agent
    )
    if compensation_differentiating_scope:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Compensation acceptă numai scope agregat de firmă.",
        )
    if module in {ModuleId.FINANCE, ModuleId.PLANNING} and scope.agent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Filtrul Agent nu este compatibil cu modulul {module.value}.",
        )
    snapshot = await repository.resolve_snapshot(scope)
    unavailable_domains = unavailable_source_domains(module, snapshot)
    if unavailable_domains:
        return unavailable_module_response(module, scope, snapshot, unavailable_domains)
    base_task = asyncio.create_task(repository.get_module(module, scope))
    temporal_tasks = {
        comparison: asyncio.create_task(
            repository.get_module(
                module,
                scope.model_copy(
                    update={
                        "comparison": (
                            ComparisonMode.PREVIOUS_MONTH
                            if comparison == "previous-period"
                            else ComparisonMode.PREVIOUS_YEAR
                        )
                    }
                ),
            )
        )
        for comparison in window.requested_comparisons
        if comparison in {"previous-period", "previous-year"}
    }
    data, *comparison_responses = await asyncio.gather(base_task, *temporal_tasks.values())
    comparison_data = dict(zip(temporal_tasks, comparison_responses, strict=True))
    snapshot_id = data.meta.analytical_snapshot_id
    if snapshot_id and any(response.meta.analytical_snapshot_id != snapshot_id for response in comparison_responses):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Snapshot is no longer eligible.",
        )
    return apply_module_window(data, window, comparison_data)


@router.get("/catalog/metrics", response_model=list[MetricDefinition])
async def metric_catalog(
    _user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
) -> list[MetricDefinition]:
    return list(METRIC_CATALOG)


@router.get("/catalog", response_model=AnalyticsCatalogResponse)
async def analytics_catalog(
    _user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
) -> AnalyticsCatalogResponse:
    return ANALYTICS_CATALOG
