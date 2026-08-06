from typing import Any

import pytest

from unihub_insight_api.domain import AnalyticsScope
from unihub_insight_api.repositories.postgres import PostgresAnalyticsRepository


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *params: Any) -> dict[str, int]:
        self.calls.append((query, params))
        return {"total_target": 0}

    async def fetch(self, query: str, *params: Any) -> list[Any]:
        self.calls.append((query, params))
        return []


class AcquireContext:
    def __init__(self, connection: RecordingConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> RecordingConnection:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class RecordingPool:
    def __init__(self) -> None:
        self.connection = RecordingConnection()

    def acquire(self) -> AcquireContext:
        return AcquireContext(self.connection)


@pytest.mark.parametrize("method_name", ["_fetch_summary", "_fetch_performance"])
async def test_agent_scope_uses_agent_targets(method_name: str) -> None:
    pool = RecordingPool()
    repository = PostgresAnalyticsRepository(pool)  # type: ignore[arg-type]
    scope = AnalyticsScope(period="2026-07", agent="ACSINTED")

    await getattr(repository, method_name)(scope, scope.period)

    query, params = pool.connection.calls[-1]
    assert "FROM agent_targets" in query
    assert "FROM store_targets" not in query
    assert params[-1] == ["ACSINTED"]


@pytest.mark.parametrize("method_name", ["_fetch_summary", "_fetch_performance"])
async def test_non_agent_scope_uses_store_targets(method_name: str) -> None:
    pool = RecordingPool()
    repository = PostgresAnalyticsRepository(pool)  # type: ignore[arg-type]
    scope = AnalyticsScope(period="2026-07", stores=("ISMOLDMALL",))

    await getattr(repository, method_name)(scope, scope.period)

    query, params = pool.connection.calls[-1]
    assert "FROM store_targets" in query
    assert "FROM agent_targets" not in query
    assert params == ("2026-07", ["ISMOLDMALL"])
