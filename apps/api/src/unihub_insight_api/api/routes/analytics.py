from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from unihub_insight_api.api.dependencies import RepositoryDependency, ScopeDependency
from unihub_insight_api.auth import require_capability
from unihub_insight_api.domain import (
    Capability,
    FilterOptionsResponse,
    MetricDefinition,
    ModuleAnalyticsResponse,
    ModuleId,
    OverviewResponse,
    UserContext,
)
from unihub_insight_api.services import METRIC_CATALOG

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
    user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
) -> ModuleAnalyticsResponse:
    required = MODULE_CAPABILITIES[module]
    if required not in user.capabilities:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Capability {required.value} is required.",
        )
    if module in {ModuleId.FINANCE, ModuleId.PLANNING} and scope.agent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Filtrul Agent nu este compatibil cu modulul {module.value}.",
        )
    return await repository.get_module(module, scope)


@router.get("/catalog/metrics", response_model=list[MetricDefinition])
async def metric_catalog(
    _user: Annotated[UserContext, Depends(require_capability(Capability.ANALYTICS))],
) -> list[MetricDefinition]:
    return list(METRIC_CATALOG)
