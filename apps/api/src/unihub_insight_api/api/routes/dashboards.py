from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from unihub_insight_api.api.dependencies import AnalyticsUserDependency, DashboardStoreDependency
from unihub_insight_api.domain import (
    DashboardCreateRequest,
    DashboardDocument,
    DashboardListResponse,
    DashboardSubject,
    DashboardUpdateRequest,
    FilterPreset,
    FilterPresetCreateRequest,
    FilterPresetUpdateRequest,
)
from unihub_insight_api.repositories.dashboards import (
    DashboardConflictError,
    DashboardNotFoundError,
)
from unihub_insight_api.services.dashboard_validation import (
    DashboardCapabilityError,
    DashboardValidationError,
    user_can_admin,
    user_can_read,
    user_can_write,
    validate_dashboard,
)

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


def _validate(request: DashboardCreateRequest, user: AnalyticsUserDependency) -> None:
    try:
        validate_dashboard(request, user)
    except DashboardCapabilityError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except DashboardValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Dashboard configuration is invalid.", "errors": list(exc.errors)},
        ) from exc


@router.get("", response_model=DashboardListResponse)
async def list_dashboards(store: DashboardStoreDependency, user: AnalyticsUserDependency) -> DashboardListResponse:
    await store.remember_user(user.subject, user.email, user.name)
    items = await store.list_for_user(user.subject)
    return DashboardListResponse(items=[item for item in items if user_can_read(item, user)])


@router.post("", response_model=DashboardDocument, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    request: DashboardCreateRequest, store: DashboardStoreDependency, user: AnalyticsUserDependency
) -> DashboardDocument:
    await store.remember_user(user.subject, user.email, user.name)
    _validate(request, user)
    return await store.create(user.subject, request)


@router.get("/subjects", response_model=list[DashboardSubject])
async def list_dashboard_subjects(
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> list[DashboardSubject]:
    await store.remember_user(user.subject, user.email, user.name)
    return await store.list_subjects()


@router.get("/presets", response_model=list[FilterPreset])
async def list_filter_presets(
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> list[FilterPreset]:
    return await store.list_filter_presets(user.subject)


@router.post("/presets", response_model=FilterPreset, status_code=status.HTTP_201_CREATED)
async def create_filter_preset(
    request: FilterPresetCreateRequest,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> FilterPreset:
    return await store.create_filter_preset(user.subject, request)


@router.put("/presets/{preset_id}", response_model=FilterPreset)
async def update_filter_preset(
    preset_id: str,
    request: FilterPresetUpdateRequest,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> FilterPreset:
    try:
        return await store.update_filter_preset(preset_id, user.subject, request)
    except DashboardConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Preset was modified.") from exc
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found.") from exc


@router.delete("/presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter_preset(
    preset_id: str,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> Response:
    if not await store.delete_filter_preset(preset_id, user.subject):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{dashboard_id}", response_model=DashboardDocument)
async def get_dashboard(
    dashboard_id: str, store: DashboardStoreDependency, user: AnalyticsUserDependency
) -> DashboardDocument:
    await store.remember_user(user.subject, user.email, user.name)
    document = await store.get(dashboard_id)
    if document is None or not user_can_read(document, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    return document


@router.get("/{dashboard_id}/versions", response_model=list[DashboardDocument])
async def list_dashboard_versions(
    dashboard_id: str,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> list[DashboardDocument]:
    document = await store.get(dashboard_id)
    if document is None or not user_can_read(document, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    return await store.list_versions(dashboard_id)


@router.put("/{dashboard_id}", response_model=DashboardDocument)
async def update_dashboard(
    dashboard_id: str,
    request: DashboardUpdateRequest,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> DashboardDocument:
    await store.remember_user(user.subject, user.email, user.name)
    current = await store.get(dashboard_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    if not user_can_write(current, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dashboard is read-only.")
    sharing_changed = (
        request.acl != current.acl
        or request.scope_ceiling != current.scope_ceiling
        or request.visibility != current.visibility
    )
    if sharing_changed and not user_can_admin(current, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dashboard sharing requires owner or admin permission.",
        )
    _validate(request, user)
    try:
        return await store.update(dashboard_id, request, user.subject)
    except DashboardConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dashboard was modified by another request.",
        ) from exc
    except DashboardNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.") from exc


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: str, store: DashboardStoreDependency, user: AnalyticsUserDependency
) -> Response:
    current = await store.get(dashboard_id)
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    if not user_can_admin(current, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Dashboard deletion requires admin permission."
        )
    if not await store.delete(dashboard_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
