from __future__ import annotations

import csv
import io
import os
import re
from contextlib import suppress
from pathlib import Path
from typing import cast

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from unihub_insight_api.api.dependencies import (
    AnalyticsUserDependency,
    DashboardStoreDependency,
    RepositoryDependency,
    ScopeDependency,
)
from unihub_insight_api.config import Settings
from unihub_insight_api.domain import (
    InspectRequest,
    InspectResponse,
    QueryBatchRequest,
    QueryBatchResponse,
    QueryErrorCode,
)
from unihub_insight_api.services.dashboard_validation import (
    dashboard_allows_scope,
    user_can_read,
    validate_batch_for_dashboard,
)
from unihub_insight_api.services.excel_export import query_workbook
from unihub_insight_api.services.metric_catalog import METRIC_CATALOG
from unihub_insight_api.services.query_planner import (
    SnapshotConflictError,
    dataset_page,
    execute_query_batch,
    resolve_query_scope,
)

router = APIRouter(prefix="/api/v1/query", tags=["query"])
METRICS = {metric.id: metric for metric in METRIC_CATALOG}


def _safe_csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return f"'{value}"
    return value


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    return (normalized or "widget")[:80]


def _remove_file(path: Path) -> None:
    with suppress(FileNotFoundError):
        os.unlink(path)


def _error_status(code: QueryErrorCode) -> int:
    return {
        QueryErrorCode.UNAUTHORIZED: status.HTTP_403_FORBIDDEN,
        QueryErrorCode.INVALID_QUERY: status.HTTP_422_UNPROCESSABLE_CONTENT,
        QueryErrorCode.DEADLINE_EXCEEDED: status.HTTP_504_GATEWAY_TIMEOUT,
        QueryErrorCode.UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
        QueryErrorCode.INTERNAL: status.HTTP_503_SERVICE_UNAVAILABLE,
    }[code]


async def _authorize_dashboard(
    request: QueryBatchRequest,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
    scope: ScopeDependency,
) -> None:
    if request.dashboard_id is None:
        return
    document = await store.get(request.dashboard_id)
    if document is None or not user_can_read(document, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found.")
    if not dashboard_allows_scope(document, scope):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Scope exceeds dashboard ceiling.")
    if any(not dashboard_allows_scope(document, resolve_query_scope(scope, query)) for query in request.widgets):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Widget scope exceeds dashboard ceiling.")
    try:
        validate_batch_for_dashboard(document, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


@router.post("/batch", response_model=QueryBatchResponse)
async def query_batch(
    body: QueryBatchRequest,
    request: Request,
    repository: RepositoryDependency,
    scope: ScopeDependency,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> QueryBatchResponse:
    await _authorize_dashboard(body, store, user, scope)
    settings = cast(Settings, request.app.state.settings)
    try:
        return await execute_query_batch(
            repository,
            body,
            scope,
            user,
            deadline_ms=settings.batch_deadline_ms,
        )
    except SnapshotConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Snapshot is no longer eligible.", "current_snapshot_id": exc.current},
        ) from exc


@router.post("/inspect", response_model=InspectResponse)
async def inspect_query(
    body: InspectRequest,
    request: Request,
    repository: RepositoryDependency,
    scope: ScopeDependency,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> InspectResponse:
    batch_request = QueryBatchRequest(
        snapshot_id=body.snapshot_id,
        dashboard_id=body.dashboard_id,
        widgets=[body.query],
    )
    await _authorize_dashboard(batch_request, store, user, scope)
    settings = cast(Settings, request.app.state.settings)
    try:
        batch = await execute_query_batch(
            repository,
            batch_request,
            scope,
            user,
            deadline_ms=settings.batch_deadline_ms,
        )
    except SnapshotConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Snapshot is no longer eligible.", "current_snapshot_id": exc.current},
        ) from exc
    result = batch.results[0]
    if result.error is not None:
        raise HTTPException(status_code=_error_status(result.error.code), detail=result.error.message)
    if result.dataset is None or result.meta is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Dataset unavailable.")
    total_rows = len(result.dataset.rows)
    await store.record_query_audit(
        actor_subject=user.subject,
        action="inspect",
        dashboard_id=body.dashboard_id,
        widget_id=body.query.widget_id,
        snapshot_id=batch.snapshot.id,
        metric_id=body.query.metric_id,
        row_count=min(total_rows, body.page_size),
    )
    return InspectResponse(
        snapshot=batch.snapshot,
        query=body.query,
        dataset=dataset_page(result.dataset, body.page, body.page_size),
        meta=result.meta,
        page=body.page,
        page_size=body.page_size,
        total_rows=total_rows,
    )


@router.post("/export.csv")
async def export_query_csv(
    body: InspectRequest,
    request: Request,
    repository: RepositoryDependency,
    scope: ScopeDependency,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> Response:
    batch_request = QueryBatchRequest(
        snapshot_id=body.snapshot_id,
        dashboard_id=body.dashboard_id,
        widgets=[body.query],
    )
    await _authorize_dashboard(batch_request, store, user, scope)
    settings = cast(Settings, request.app.state.settings)
    try:
        batch = await execute_query_batch(
            repository,
            batch_request,
            scope,
            user,
            deadline_ms=settings.batch_deadline_ms,
        )
    except SnapshotConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Snapshot is no longer eligible.", "current_snapshot_id": exc.current},
        ) from exc
    result = batch.results[0]
    if result.error is not None:
        raise HTTPException(status_code=_error_status(result.error.code), detail=result.error.message)
    if result.dataset is None or result.meta is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Dataset unavailable.")

    dataset = result.dataset
    dimensions = [dimension.id for dimension in dataset.dimensions]
    metadata_columns = [
        "_analytical_snapshot_id",
        "_source_generation",
        "_authority",
        "_authority_head",
        "_status",
        "_source_period",
        "_cutoff",
        "_as_of",
        "_is_final",
        "_coverage_numerator",
        "_coverage_denominator",
        "_contract_version",
        "_rule_version",
        "_produced_at",
        "_warnings",
    ]
    source_items = sorted(result.meta.sources.items())
    for domain, _source in source_items:
        prefix = f"_source_{_safe_filename(domain)}"
        metadata_columns.extend(
            [
                prefix,
                f"{prefix}_generation",
                f"{prefix}_authority",
                f"{prefix}_head",
                f"{prefix}_status",
                f"{prefix}_period",
                f"{prefix}_cutoff",
                f"{prefix}_as_of",
                f"{prefix}_is_final",
                f"{prefix}_coverage_numerator",
                f"{prefix}_coverage_denominator",
                f"{prefix}_contract_version",
                f"{prefix}_rule_version",
                f"{prefix}_produced_at",
                f"{prefix}_warnings",
            ]
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([*dimensions, *metadata_columns])
    source = result.meta.source
    metadata = [
        batch.snapshot.id,
        source.source_generation,
        source.authority,
        source.authority_head,
        source.status.value,
        source.period,
        source.cutoff,
        source.as_of,
        source.is_final,
        source.coverage_numerator,
        source.coverage_denominator,
        source.contract_version,
        source.rule_version,
        source.produced_at,
        ";".join(source.warnings),
    ]
    for _domain, item in source_items:
        metadata.extend(
            [
                item.source,
                item.source_generation,
                item.authority,
                item.authority_head,
                item.status.value,
                item.period,
                item.cutoff,
                item.as_of,
                item.is_final,
                item.coverage_numerator,
                item.coverage_denominator,
                item.contract_version,
                item.rule_version,
                item.produced_at,
                ";".join(item.warnings),
            ]
        )
    for row in dataset.rows:
        writer.writerow(
            [_safe_csv_value(row.get(dimension)) for dimension in dimensions]
            + [_safe_csv_value(value) for value in metadata]
        )
    content = output.getvalue().encode("utf-8-sig")
    await store.record_query_audit(
        actor_subject=user.subject,
        action="export.csv",
        dashboard_id=body.dashboard_id,
        widget_id=body.query.widget_id,
        snapshot_id=batch.snapshot.id,
        metric_id=body.query.metric_id,
        row_count=len(dataset.rows),
    )
    filename = f"unihub-insight-{_safe_filename(body.query.widget_id)}-{scope.period}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/export.xlsx", response_class=FileResponse)
async def export_query_xlsx(
    body: InspectRequest,
    request: Request,
    repository: RepositoryDependency,
    scope: ScopeDependency,
    store: DashboardStoreDependency,
    user: AnalyticsUserDependency,
) -> FileResponse:
    batch_request = QueryBatchRequest(
        snapshot_id=body.snapshot_id,
        dashboard_id=body.dashboard_id,
        widgets=[body.query],
    )
    await _authorize_dashboard(batch_request, store, user, scope)
    settings = cast(Settings, request.app.state.settings)
    try:
        batch = await execute_query_batch(
            repository,
            batch_request,
            scope,
            user,
            deadline_ms=settings.batch_deadline_ms,
        )
    except SnapshotConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Snapshot is no longer eligible.", "current_snapshot_id": exc.current},
        ) from exc
    result = batch.results[0]
    if result.error is not None:
        raise HTTPException(status_code=_error_status(result.error.code), detail=result.error.message)
    if result.dataset is None or result.meta is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Dataset unavailable.")
    metric = METRICS.get(body.query.metric_id)
    if metric is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Metric unavailable.")

    dataset = result.dataset
    path = query_workbook(dataset, result.meta, batch.snapshot, body.query, metric)
    await store.record_query_audit(
        actor_subject=user.subject,
        action="export.xlsx",
        dashboard_id=body.dashboard_id,
        widget_id=body.query.widget_id,
        snapshot_id=batch.snapshot.id,
        metric_id=body.query.metric_id,
        row_count=len(dataset.rows),
    )
    filename = f"unihub-insight-{_safe_filename(body.query.widget_id)}-{scope.period}.xlsx"
    return FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(_remove_file, path),
        headers={"Cache-Control": "private, no-store"},
    )
