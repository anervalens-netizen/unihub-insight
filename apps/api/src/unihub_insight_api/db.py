from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from unihub_insight_api.config import Settings


@runtime_checkable
class PoolLike(Protocol):
    def acquire(self) -> Any: ...

    async def close(self) -> None: ...


async def _create_pool(
    *,
    dsn: str,
    min_size: int,
    max_size: int,
    timeout_ms: int,
    read_only: bool,
    application_name: str,
) -> PoolLike:
    try:
        import asyncpg
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise RuntimeError("asyncpg is required for PostgreSQL mode") from exc

    server_settings = {
        "application_name": application_name,
        "statement_timeout": str(timeout_ms),
        "lock_timeout": "1000",
        "idle_in_transaction_session_timeout": "5000",
        "timezone": "UTC",
    }
    if read_only:
        server_settings["default_transaction_read_only"] = "on"
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=timeout_ms / 1000,
        server_settings=server_settings,
    )


async def create_pool(settings: Settings) -> PoolLike:
    if not settings.database_url:
        raise RuntimeError("database_url is required to create the analytics pool")
    return await _create_pool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        timeout_ms=settings.statement_timeout_ms,
        read_only=True,
        application_name="unihub-insight-analytics",
    )


async def create_metadata_pool(settings: Settings) -> PoolLike:
    if not settings.metadata_database_url:
        raise RuntimeError("metadata_database_url is required to create the metadata pool")
    return await _create_pool(
        dsn=settings.metadata_database_url,
        min_size=1,
        max_size=settings.metadata_pool_max_size,
        timeout_ms=settings.statement_timeout_ms,
        read_only=False,
        application_name="unihub-insight-metadata",
    )


async def close_pool(pool: PoolLike | None) -> None:
    if pool is not None:
        await pool.close()


async def check_pool(pool: PoolLike | None, *, expect_read_only: bool) -> bool:
    if pool is None:
        return False
    try:
        async with pool.acquire() as connection:
            value: Any = await connection.fetchval("SELECT current_setting('transaction_read_only') = 'on'")
        return bool(value) is expect_read_only
    except Exception:
        return False
