from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from unihub_insight_api.api.dependencies import ModuleWindowDependency, RepositoryDependency, ScopeDependency
from unihub_insight_api.auth import require_capability
from unihub_insight_api.domain import Capability, ModuleId, UserContext
from unihub_insight_api.services.excel_export import (
    module_workbook,
    monthly_review_workbook,
    overview_workbook,
)
from unihub_insight_api.services.module_window import apply_module_window

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])

MODULE_CAPABILITIES: dict[ModuleId, Capability] = {
    ModuleId.SALES: Capability.ANALYTICS,
    ModuleId.PERFORMANCE: Capability.ANALYTICS,
    ModuleId.CAMPAIGNS: Capability.ANALYTICS,
    ModuleId.WORKFORCE: Capability.MANAGEMENT,
    ModuleId.COMPENSATION: Capability.HR,
    ModuleId.FINANCE: Capability.PNL,
    ModuleId.PLANNING: Capability.MANAGEMENT,
}

REPORT_SECTIONS = {
    "all",
    "summary",
    "trend",
    "companies",
    "managers",
    "stores",
    "agents",
    "categories",
    "products",
    "returns",
    "methodology",
}


def _remove_file(path: Path) -> None:
    with suppress(FileNotFoundError):
        os.unlink(path)


def _response(path: Path, filename: str) -> FileResponse:
    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(_remove_file, path),
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/overview.xlsx", response_class=FileResponse)
async def export_overview(
    repository: RepositoryDependency,
    scope: ScopeDependency,
    _user: Annotated[
        UserContext,
        Depends(require_capability(Capability.ANALYTICS)),
    ],
) -> FileResponse:
    data = await repository.get_overview(scope)
    return _response(
        overview_workbook(data),
        f"unihub-insight-overview-{scope.period}.xlsx",
    )


@router.get("/modules/{module}.xlsx", response_class=FileResponse)
async def export_module(
    module: ModuleId,
    repository: RepositoryDependency,
    scope: ScopeDependency,
    window: ModuleWindowDependency,
    user: Annotated[
        UserContext,
        Depends(require_capability(Capability.ANALYTICS)),
    ],
) -> FileResponse:
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
    data = apply_module_window(await repository.get_module(module, scope), window)
    return _response(
        module_workbook(data),
        f"unihub-insight-{module.value}-{scope.period}.xlsx",
    )


@router.get("/monthly-review.xlsx", response_class=FileResponse)
async def export_monthly_review(
    repository: RepositoryDependency,
    scope: ScopeDependency,
    _user: Annotated[
        UserContext,
        Depends(require_capability(Capability.ANALYTICS)),
    ],
    recent_months: Annotated[int, Query(ge=3, le=12)] = 3,
    section: Annotated[str, Query(max_length=40)] = "all",
) -> FileResponse:
    normalized_section = section.casefold()
    if normalized_section not in REPORT_SECTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Secțiunea de export nu este suportată.",
        )
    data = await repository.get_monthly_review(scope, recent_months)
    suffix = "complet" if normalized_section == "all" else normalized_section
    return _response(
        monthly_review_workbook(data, normalized_section),
        f"unihub-insight-raport-lunar-{scope.period}-{suffix}.xlsx",
    )
