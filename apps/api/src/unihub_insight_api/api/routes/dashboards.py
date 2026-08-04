from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from unihub_insight_api.api.dependencies import (
    AnalyticsUserDependency,
    DashboardStoreDependency,
)
from unihub_insight_api.domain import (
    Capability,
    DashboardCreateRequest,
    DashboardDocument,
    DashboardListResponse,
    DashboardUpdateRequest,
    DashboardVisibility,
)
from unihub_insight_api.repositories.dashboards import (
    DashboardConflictError,
    DashboardNotFoundError,
)


router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


def _can_read(document: DashboardDocument, subject: str) -> bool:
    return document.owner_subject == subject or document.visibility is DashboardVisibility.SHARED


def _can_write(document: DashboardDocument, user: AnalyticsUserDependency) -> bool:
    return document.owner_subject == user.subject or Capability.ADMIN in user.capabilities


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> DashboardListResponse:
    return DashboardListResponse(items=await store.list_for_user(user.subject))


@router.post("", response_model=DashboardDocument, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    request: DashboardCreateRequest,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> DashboardDocument:
    return await store.create(user.subject, request)


@router.get("/{dashboard_id}", response_model=DashboardDocument)
async def get_dashboard(
    dashboard_id: str,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> DashboardDocument:
    document = await store.get(dashboard_id)
    if document is None or not _can_read(document, user.subject):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    return document


@router.put("/{dashboard_id}", response_model=DashboardDocument)
async def update_dashboard(
    dashboard_id: str,
    request: DashboardUpdateRequest,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> DashboardDocument:
    current = await store.get(dashboard_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    if not _can_write(current, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dashboard is read-only.")
    try:
        return await store.update(dashboard_id, request)
    except DashboardConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dashboard was modified by another request.",
        ) from exc
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.") from exc


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: str,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> Response:
    current = await store.get(dashboard_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    if not _can_write(current, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dashboard is read-only.")
    if not await store.delete(dashboard_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
