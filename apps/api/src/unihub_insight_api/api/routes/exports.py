from __future__ import annotations

import os
from contextlib import suppress
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from unihub_insight_api.api.dependencies import (
    DashboardStoreDependency,
    ModuleWindowDependency,
    RepositoryDependency,
    ScopeDependency,
)
from unihub_insight_api.auth import require_capability
from unihub_insight_api.domain import Capability, ModuleId, UserContext
from unihub_insight_api.services.excel_export import (
    module_workbook,
    monthly_review_workbook,
    overview_workbook,
)
from unihub_insight_api.services.module_availability import unavailable_source_domains
from unihub_insight_api.services.module_window import allowed_module_window, apply_module_window

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


def _snapshot_id(data: object, period: str) -> str:
    meta = getattr(data, "meta", None)
    value = getattr(meta, "analytical_snapshot_id", None)
    return str(value) if value else f"legacy-{period}"


def _row_count(data: object, fields: tuple[str, ...]) -> int:
    return sum(len(getattr(data, field, ())) for field in fields)


@router.get("/overview.xlsx", response_class=FileResponse)
async def export_overview(
    repository: RepositoryDependency,
    scope: ScopeDependency,
    store: DashboardStoreDependency,
    user: Annotated[
        UserContext,
        Depends(require_capability(Capability.ANALYTICS)),
    ],
) -> FileResponse:
    data = await repository.get_overview(scope)
    path = overview_workbook(data)
    await store.record_query_audit(
        actor_subject=user.subject,
        action="export.overview.xlsx",
        dashboard_id=None,
        widget_id="overview",
        snapshot_id=_snapshot_id(data, scope.period),
        metric_id="overview.*",
        row_count=_row_count(data, ("kpis", "daily", "contribution", "performance", "alerts")),
    )
    return _response(
        path,
        f"unihub-insight-overview-{scope.period}.xlsx",
    )


@router.get("/modules/{module}.xlsx", response_class=FileResponse)
async def export_module(
    module: ModuleId,
    repository: RepositoryDependency,
    scope: ScopeDependency,
    window: ModuleWindowDependency,
    store: DashboardStoreDependency,
    user: Annotated[
        UserContext,
        Depends(require_capability(Capability.ANALYTICS)),
    ],
    snapshot_id: Annotated[str | None, Query(max_length=200)] = None,
) -> FileResponse:
    window = allowed_module_window(module, window)
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
    if snapshot_id and snapshot_id != snapshot.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Snapshot is no longer eligible.",
        )
    unavailable_domains = unavailable_source_domains(module, snapshot)
    if unavailable_domains:
        names = ", ".join(domain.value for domain in unavailable_domains)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sursele {names} nu sunt disponibile în snapshotul eligibil.",
        )
    data = apply_module_window(await repository.get_module(module, scope), window)
    if data.meta.analytical_snapshot_id != snapshot.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Snapshot is no longer eligible.",
        )
    path = module_workbook(data)
    await store.record_query_audit(
        actor_subject=user.subject,
        action="export.module.xlsx",
        dashboard_id=None,
        widget_id=f"module:{module.value}",
        snapshot_id=_snapshot_id(data, scope.period),
        metric_id=f"{module.value}.*",
        row_count=_row_count(data, ("kpis", "trend", "distribution", "breakdown", "matrix", "alerts")),
    )
    return _response(
        path,
        f"unihub-insight-{module.value}-{scope.period}.xlsx",
    )


@router.get("/monthly-review.xlsx", response_class=FileResponse)
async def export_monthly_review(
    repository: RepositoryDependency,
    scope: ScopeDependency,
    store: DashboardStoreDependency,
    user: Annotated[
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
    path = monthly_review_workbook(data, normalized_section)
    await store.record_query_audit(
        actor_subject=user.subject,
        action="export.monthly.xlsx",
        dashboard_id=None,
        widget_id=f"monthly-review:{suffix}",
        snapshot_id=_snapshot_id(data, scope.period),
        metric_id="monthly-review.*",
        row_count=_row_count(
            data,
            (
                "executive",
                "trend",
                "seasonality",
                "drivers",
                "companies",
                "managers",
                "stores",
                "categories",
                "products",
                "returns",
                "agents",
                "alerts",
                "methodology",
            ),
        ),
    )
    return _response(
        path,
        f"unihub-insight-raport-lunar-{scope.period}-{suffix}.xlsx",
    )
