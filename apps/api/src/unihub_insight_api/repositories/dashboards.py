from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from unihub_insight_api.domain import (
    DashboardCreateRequest,
    DashboardDocument,
    DashboardUpdateRequest,
    DashboardVisibility,
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
    ) -> DashboardDocument: ...

    async def delete(self, dashboard_id: str) -> bool: ...


class MemoryDashboardStore:
    def __init__(self) -> None:
        self._items: dict[str, DashboardDocument] = {}
        self._lock = asyncio.Lock()

    async def list_for_user(self, subject: str) -> list[DashboardDocument]:
        async with self._lock:
            return sorted(
                (
                    item
                    for item in self._items.values()
                    if item.owner_subject == subject
                    or item.visibility is DashboardVisibility.SHARED
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
            owner_subject=subject,
            version=1,
            created_at=now,
            updated_at=now,
            **request.model_dump(),
        )
        async with self._lock:
            self._items[document.id] = document
        return document

    async def update(
        self,
        dashboard_id: str,
        request: DashboardUpdateRequest,
    ) -> DashboardDocument:
        async with self._lock:
            current = self._items.get(dashboard_id)
            if current is None:
                raise DashboardNotFoundError(dashboard_id)
            if current.version != request.version:
                raise DashboardConflictError(dashboard_id)
            payload = request.model_dump(exclude={"version"})
            updated = current.model_copy(
                update={
                    **payload,
                    "version": current.version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
            self._items[dashboard_id] = updated
            return updated

    async def delete(self, dashboard_id: str) -> bool:
        async with self._lock:
            return self._items.pop(dashboard_id, None) is not None


class PostgresDashboardStore:
    def __init__(self, pool: Any):
        self.pool = pool

    @staticmethod
    def _document(row: Any) -> DashboardDocument:
        widgets = row["widgets"]
        if isinstance(widgets, str):
            widgets = json.loads(widgets)
        return DashboardDocument(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            owner_subject=row["owner_subject"],
            visibility=row["visibility"],
            version=row["version"],
            widgets=widgets,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_for_user(self, subject: str) -> list[DashboardDocument]:
        async with self.pool.acquire() as connection:
            rows: Sequence[Any] = await connection.fetch(
                """
                SELECT id, name, description, owner_subject, visibility, version,
                       widgets, created_at, updated_at
                FROM insight.dashboards
                WHERE owner_subject = $1 OR visibility = 'shared'
                ORDER BY updated_at DESC
                """,
                subject,
            )
        return [self._document(row) for row in rows]

    async def get(self, dashboard_id: str) -> DashboardDocument | None:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT id, name, description, owner_subject, visibility, version,
                       widgets, created_at, updated_at
                FROM insight.dashboards WHERE id = $1
                """,
                dashboard_id,
            )
        return self._document(row) if row else None

    async def create(
        self,
        subject: str,
        request: DashboardCreateRequest,
    ) -> DashboardDocument:
        dashboard_id = uuid.uuid4().hex
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO insight.dashboards
                    (id, name, description, owner_subject, visibility, widgets)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                RETURNING id, name, description, owner_subject, visibility, version,
                          widgets, created_at, updated_at
                """,
                dashboard_id,
                request.name,
                request.description,
                subject,
                request.visibility.value,
                json.dumps([widget.model_dump(mode="json") for widget in request.widgets]),
            )
        if row is None:
            raise RuntimeError("Dashboard insert returned no row")
        return self._document(row)

    async def update(
        self,
        dashboard_id: str,
        request: DashboardUpdateRequest,
    ) -> DashboardDocument:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                UPDATE insight.dashboards
                SET name = $2,
                    description = $3,
                    visibility = $4,
                    widgets = $5::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE id = $1 AND version = $6
                RETURNING id, name, description, owner_subject, visibility, version,
                          widgets, created_at, updated_at
                """,
                dashboard_id,
                request.name,
                request.description,
                request.visibility.value,
                json.dumps([widget.model_dump(mode="json") for widget in request.widgets]),
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
        return self._document(row)

    async def delete(self, dashboard_id: str) -> bool:
        async with self.pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM insight.dashboards WHERE id = $1",
                dashboard_id,
            )
        return result == "DELETE 1"
