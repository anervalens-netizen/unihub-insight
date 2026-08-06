from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from unihub_insight_api.domain import (
    DashboardAclEntry,
    DashboardCreateRequest,
    DashboardDocument,
    DashboardScopeCeiling,
    DashboardSubject,
    DashboardUpdateRequest,
    FilterPreset,
    FilterPresetCreateRequest,
    FilterPresetUpdateRequest,
)


class DashboardConflictError(RuntimeError):
    pass


class DashboardNotFoundError(RuntimeError):
    pass


class DashboardStore(Protocol):
    async def list_for_user(self, subject: str) -> list[DashboardDocument]: ...

    async def get(self, dashboard_id: str) -> DashboardDocument | None: ...

    async def create(
        self,
        subject: str,
        request: DashboardCreateRequest,
    ) -> DashboardDocument: ...

    async def update(
        self,
        dashboard_id: str,
        request: DashboardUpdateRequest,
        actor_subject: str,
    ) -> DashboardDocument: ...

    async def delete(self, dashboard_id: str) -> bool: ...

    async def remember_user(self, subject: str, email: str | None, name: str | None) -> None: ...

    async def list_subjects(self) -> list[DashboardSubject]: ...

    async def list_versions(self, dashboard_id: str) -> list[DashboardDocument]: ...

    async def list_filter_presets(self, subject: str) -> list[FilterPreset]: ...

    async def create_filter_preset(self, subject: str, request: FilterPresetCreateRequest) -> FilterPreset: ...

    async def update_filter_preset(
        self, preset_id: str, subject: str, request: FilterPresetUpdateRequest
    ) -> FilterPreset: ...

    async def delete_filter_preset(self, preset_id: str, subject: str) -> bool: ...

    async def record_query_audit(
        self,
        *,
        actor_subject: str,
        action: str,
        dashboard_id: str | None,
        widget_id: str,
        snapshot_id: str,
        metric_id: str,
        row_count: int,
    ) -> None: ...


class MemoryDashboardStore:
    def __init__(self) -> None:
        self._items: dict[str, DashboardDocument] = {}
        self._subjects: dict[str, DashboardSubject] = {}
        self._versions: dict[str, list[DashboardDocument]] = {}
        self._presets: dict[str, FilterPreset] = {}
        self._lock = asyncio.Lock()
        self._query_audit: list[dict[str, str | int | None]] = []

    async def list_for_user(self, subject: str) -> list[DashboardDocument]:
        async with self._lock:
            return sorted(
                (
                    item
                    for item in self._items.values()
                    if item.owner_subject == subject
                    or item.visibility.value == "shared"
                    or any(entry.subject == subject for entry in item.acl)
                ),
                key=lambda item: item.updated_at,
                reverse=True,
            )

    async def get(self, dashboard_id: str) -> DashboardDocument | None:
        async with self._lock:
            return self._items.get(dashboard_id)

    async def create(
        self,
        subject: str,
        request: DashboardCreateRequest,
    ) -> DashboardDocument:
        now = datetime.now(UTC)
        document = DashboardDocument(
            id=uuid.uuid4().hex,
            name=request.name,
            description=request.description,
            owner_subject=subject,
            visibility=request.visibility,
            version=1,
            widgets=request.widgets,
            acl=request.acl,
            scope_ceiling=request.scope_ceiling,
            query_contract_version=request.query_contract_version,
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._items[document.id] = document
            self._versions[document.id] = [document]
        return document

    async def update(
        self,
        dashboard_id: str,
        request: DashboardUpdateRequest,
        actor_subject: str,
    ) -> DashboardDocument:
        del actor_subject
        async with self._lock:
            current = self._items.get(dashboard_id)
            if current is None:
                raise DashboardNotFoundError(dashboard_id)
            if current.version != request.version:
                raise DashboardConflictError(dashboard_id)
            updated = current.model_copy(
                update={
                    "name": request.name,
                    "description": request.description,
                    "visibility": request.visibility,
                    "widgets": request.widgets,
                    "acl": request.acl,
                    "scope_ceiling": request.scope_ceiling,
                    "query_contract_version": request.query_contract_version,
                    "version": current.version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._items[dashboard_id] = updated
            self._versions.setdefault(dashboard_id, []).append(updated)
            return updated

    async def delete(self, dashboard_id: str) -> bool:
        async with self._lock:
            deleted = self._items.pop(dashboard_id, None) is not None
            self._versions.pop(dashboard_id, None)
            return deleted

    async def remember_user(self, subject: str, email: str | None, name: str | None) -> None:
        self._subjects[subject] = DashboardSubject(
            subject=subject,
            email=email,
            display_name=name,
            last_seen_at=datetime.now(UTC),
        )

    async def list_subjects(self) -> list[DashboardSubject]:
        return sorted(self._subjects.values(), key=lambda item: (item.display_name or item.subject).casefold())

    async def list_versions(self, dashboard_id: str) -> list[DashboardDocument]:
        async with self._lock:
            return list(reversed(self._versions.get(dashboard_id, [])))

    async def list_filter_presets(self, subject: str) -> list[FilterPreset]:
        async with self._lock:
            return sorted(
                (item for item in self._presets.values() if item.owner_subject == subject or item.shared),
                key=lambda item: item.updated_at,
                reverse=True,
            )

    async def create_filter_preset(self, subject: str, request: FilterPresetCreateRequest) -> FilterPreset:
        now = datetime.now(UTC)
        preset = FilterPreset(
            id=uuid.uuid4().hex,
            owner_subject=subject,
            name=request.name,
            filters=request.filters,
            shared=request.shared,
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._presets[preset.id] = preset
        return preset

    async def update_filter_preset(
        self, preset_id: str, subject: str, request: FilterPresetUpdateRequest
    ) -> FilterPreset:
        async with self._lock:
            current = self._presets.get(preset_id)
            if current is None or current.owner_subject != subject:
                raise DashboardNotFoundError(preset_id)
            if current.version != request.version:
                raise DashboardConflictError(preset_id)
            updated = current.model_copy(
                update={
                    "name": request.name,
                    "filters": request.filters,
                    "shared": request.shared,
                    "version": current.version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._presets[preset_id] = updated
            return updated

    async def delete_filter_preset(self, preset_id: str, subject: str) -> bool:
        async with self._lock:
            current = self._presets.get(preset_id)
            if current is None or current.owner_subject != subject:
                return False
            del self._presets[preset_id]
            return True

    async def record_query_audit(
        self,
        *,
        actor_subject: str,
        action: str,
        dashboard_id: str | None,
        widget_id: str,
        snapshot_id: str,
        metric_id: str,
        row_count: int,
    ) -> None:
        async with self._lock:
            self._query_audit.append(
                {
                    "actor_subject": actor_subject,
                    "action": action,
                    "dashboard_id": dashboard_id,
                    "widget_id": widget_id,
                    "snapshot_id": snapshot_id,
                    "metric_id": metric_id,
                    "row_count": row_count,
                }
            )


class PostgresDashboardStore:
    def __init__(self, pool: Any):
        self.pool = pool

    @staticmethod
    def _document(row: Any, acl: Sequence[Any] = ()) -> DashboardDocument:
        widgets = row["widgets"]
        if isinstance(widgets, str):
            widgets = json.loads(widgets)
        scope_ceiling = row["scope_ceiling"]
        if isinstance(scope_ceiling, str):
            scope_ceiling = json.loads(scope_ceiling)
        return DashboardDocument(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            owner_subject=row["owner_subject"],
            visibility=row["visibility"],
            version=row["version"],
            widgets=widgets,
            acl=[DashboardAclEntry(subject=item["subject"], permission=item["permission"]) for item in acl],
            scope_ceiling=DashboardScopeCeiling.model_validate(scope_ceiling),
            query_contract_version=row["query_contract_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    async def _acl_by_dashboard(connection: Any, dashboard_ids: Sequence[str]) -> dict[str, list[Any]]:
        if not dashboard_ids:
            return {}
        rows = await connection.fetch(
            """
            SELECT dashboard_id, subject, permission
            FROM insight.dashboard_acl
            WHERE dashboard_id = ANY($1::text[])
            ORDER BY dashboard_id, subject
            """,
            list(dashboard_ids),
        )
        result: dict[str, list[Any]] = {}
        for row in rows:
            result.setdefault(str(row["dashboard_id"]), []).append(row)
        return result

    async def list_for_user(self, subject: str) -> list[DashboardDocument]:
        async with self.pool.acquire() as connection:
            rows: Sequence[Any] = await connection.fetch(
                """
                SELECT dashboard.id, dashboard.name, dashboard.description,
                       dashboard.owner_subject, dashboard.visibility, dashboard.version,
                       dashboard.widgets, dashboard.scope_ceiling,
                       dashboard.query_contract_version,
                       dashboard.created_at, dashboard.updated_at
                FROM insight.dashboards dashboard
                WHERE dashboard.owner_subject = $1
                   OR dashboard.visibility = 'shared'
                   OR EXISTS (
                       SELECT 1 FROM insight.dashboard_acl acl
                       WHERE acl.dashboard_id = dashboard.id AND acl.subject = $1
                   )
                ORDER BY dashboard.updated_at DESC
                """,
                subject,
            )
            acl = await self._acl_by_dashboard(connection, [str(row["id"]) for row in rows])
        return [self._document(row, acl.get(str(row["id"]), ())) for row in rows]

    async def get(self, dashboard_id: str) -> DashboardDocument | None:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT id, name, description, owner_subject, visibility, version,
                       widgets, scope_ceiling, query_contract_version,
                       created_at, updated_at
                FROM insight.dashboards WHERE id = $1
                """,
                dashboard_id,
            )
            acl = await self._acl_by_dashboard(connection, [dashboard_id] if row else [])
        return self._document(row, acl.get(dashboard_id, ())) if row else None

    async def create(
        self,
        subject: str,
        request: DashboardCreateRequest,
    ) -> DashboardDocument:
        dashboard_id = uuid.uuid4().hex
        async with self.pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """
                    INSERT INTO insight.dashboards
                        (id, name, description, owner_subject, visibility, widgets,
                         scope_ceiling, query_contract_version)
                    VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
                    RETURNING id, name, description, owner_subject, visibility, version,
                              widgets, scope_ceiling, query_contract_version,
                              created_at, updated_at
                    """,
                dashboard_id,
                request.name,
                request.description,
                subject,
                request.visibility.value,
                json.dumps([widget.model_dump(mode="json") for widget in request.widgets]),
                request.scope_ceiling.model_dump_json(),
                request.query_contract_version,
            )
            if row is None:
                raise RuntimeError("Dashboard insert returned no row")
            if request.acl:
                await connection.executemany(
                    """
                        INSERT INTO insight.dashboard_acl
                            (dashboard_id, subject, permission, granted_by_subject)
                        VALUES ($1, $2, $3, $4)
                        """,
                    [(dashboard_id, entry.subject, entry.permission.value, subject) for entry in request.acl],
                )
            acl = await self._acl_by_dashboard(connection, [dashboard_id])
            document = self._document(row, acl.get(dashboard_id, ()))
            await connection.execute(
                """
                    INSERT INTO insight.dashboard_versions
                        (dashboard_id, version, document, actor_subject)
                    VALUES ($1, $2, $3::jsonb, $4)
                    """,
                dashboard_id,
                document.version,
                document.model_dump_json(),
                subject,
            )
        return document

    async def update(
        self,
        dashboard_id: str,
        request: DashboardUpdateRequest,
        actor_subject: str,
    ) -> DashboardDocument:
        async with self.pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """
                    UPDATE insight.dashboards
                    SET name = $2,
                        description = $3,
                        visibility = $4,
                        widgets = $5::jsonb,
                        scope_ceiling = $6::jsonb,
                        query_contract_version = $7,
                        version = version + 1,
                        updated_at = now()
                    WHERE id = $1 AND version = $8
                    RETURNING id, name, description, owner_subject, visibility, version,
                              widgets, scope_ceiling, query_contract_version,
                              created_at, updated_at
                    """,
                dashboard_id,
                request.name,
                request.description,
                request.visibility.value,
                json.dumps([widget.model_dump(mode="json") for widget in request.widgets]),
                request.scope_ceiling.model_dump_json(),
                request.query_contract_version,
                request.version,
            )
            if row is None:
                exists = await connection.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM insight.dashboards WHERE id = $1)",
                    dashboard_id,
                )
                if exists:
                    raise DashboardConflictError(dashboard_id)
                raise DashboardNotFoundError(dashboard_id)
            await connection.execute("DELETE FROM insight.dashboard_acl WHERE dashboard_id = $1", dashboard_id)
            if request.acl:
                await connection.executemany(
                    """
                        INSERT INTO insight.dashboard_acl
                            (dashboard_id, subject, permission, granted_by_subject)
                        VALUES ($1, $2, $3, $4)
                        """,
                    [(dashboard_id, entry.subject, entry.permission.value, actor_subject) for entry in request.acl],
                )
            acl = await self._acl_by_dashboard(connection, [dashboard_id])
            document = self._document(row, acl.get(dashboard_id, ()))
            await connection.execute(
                """
                    INSERT INTO insight.dashboard_versions
                        (dashboard_id, version, document, actor_subject)
                    VALUES ($1, $2, $3::jsonb, $4)
                    """,
                dashboard_id,
                document.version,
                document.model_dump_json(),
                actor_subject,
            )
        return document

    async def delete(self, dashboard_id: str) -> bool:
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM insight.dashboards WHERE id = $1",
                dashboard_id,
            )
        return result == "DELETE 1"

    async def remember_user(self, subject: str, email: str | None, name: str | None) -> None:
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO insight.user_directory (subject, email, display_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (subject) DO UPDATE
                SET email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    last_seen_at = now()
                """,
                subject,
                email,
                name,
            )

    async def list_subjects(self) -> list[DashboardSubject]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT subject, email, display_name, last_seen_at
                FROM insight.user_directory
                ORDER BY COALESCE(display_name, email, subject)
                """
            )
        return [DashboardSubject.model_validate(dict(row)) for row in rows]

    async def list_versions(self, dashboard_id: str) -> list[DashboardDocument]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT document
                FROM insight.dashboard_versions
                WHERE dashboard_id = $1
                ORDER BY version DESC
                """,
                dashboard_id,
            )
        documents: list[DashboardDocument] = []
        for row in rows:
            document = row["document"]
            if isinstance(document, str):
                document = json.loads(document)
            documents.append(DashboardDocument.model_validate(document))
        return documents

    @staticmethod
    def _preset(row: Any) -> FilterPreset:
        filters = row["filters"]
        if isinstance(filters, str):
            filters = json.loads(filters)
        return FilterPreset(
            id=row["id"],
            owner_subject=row["owner_subject"],
            name=row["name"],
            filters=filters,
            shared=row["shared"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_filter_presets(self, subject: str) -> list[FilterPreset]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT id, owner_subject, name, filters, shared, version, created_at, updated_at
                FROM insight.filter_presets
                WHERE owner_subject = $1 OR shared
                ORDER BY updated_at DESC
                """,
                subject,
            )
        return [self._preset(row) for row in rows]

    async def create_filter_preset(self, subject: str, request: FilterPresetCreateRequest) -> FilterPreset:
        preset_id = uuid.uuid4().hex
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO insight.filter_presets (id, owner_subject, name, filters, shared)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                RETURNING id, owner_subject, name, filters, shared, version, created_at, updated_at
                """,
                preset_id,
                subject,
                request.name,
                json.dumps(request.filters),
                request.shared,
            )
        if row is None:
            raise RuntimeError("Filter preset insert returned no row")
        return self._preset(row)

    async def update_filter_preset(
        self, preset_id: str, subject: str, request: FilterPresetUpdateRequest
    ) -> FilterPreset:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                UPDATE insight.filter_presets
                SET name = $3, filters = $4::jsonb, shared = $5,
                    version = version + 1, updated_at = now()
                WHERE id = $1 AND owner_subject = $2 AND version = $6
                RETURNING id, owner_subject, name, filters, shared, version, created_at, updated_at
                """,
                preset_id,
                subject,
                request.name,
                json.dumps(request.filters),
                request.shared,
                request.version,
            )
            if row is None:
                exists = await connection.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM insight.filter_presets WHERE id = $1 AND owner_subject = $2)",
                    preset_id,
                    subject,
                )
                if exists:
                    raise DashboardConflictError(preset_id)
                raise DashboardNotFoundError(preset_id)
        return self._preset(row)

    async def delete_filter_preset(self, preset_id: str, subject: str) -> bool:
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM insight.filter_presets WHERE id = $1 AND owner_subject = $2",
                preset_id,
                subject,
            )
        return result == "DELETE 1"

    async def record_query_audit(
        self,
        *,
        actor_subject: str,
        action: str,
        dashboard_id: str | None,
        widget_id: str,
        snapshot_id: str,
        metric_id: str,
        row_count: int,
    ) -> None:
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO insight.query_audit
                    (actor_subject, action, dashboard_id, widget_id,
                     analytical_snapshot_id, metric_id, row_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                actor_subject,
                action,
                dashboard_id,
                widget_id,
                snapshot_id,
                metric_id,
                row_count,
            )
