from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from unihub_insight_api.config import Settings


@runtime_checkable
class PoolLike(Protocol):
    def acquire(self) -> Any: ...

    async def close(self) -> None: ...


async def create_pool(settings: Settings) -> PoolLike:
    if not settings.database_url:
        raise RuntimeError("database_url is required to create the PostgreSQL pool")

    try:
        import asyncpg
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise RuntimeError(
            "asyncpg is required when UNIHUB_INSIGHT_DATA_MODE=postgres"
        ) from exc

    return await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.statement_timeout_ms / 1000,
        server_settings={
            "application_name": "unihub-insight",
            "default_transaction_read_only": "on",
            "statement_timeout": str(settings.statement_timeout_ms),
            "lock_timeout": "1000",
            "idle_in_transaction_session_timeout": "5000",
            "timezone": "UTC",
        },
    )


async def close_pool(pool: PoolLike | None) -> None:
    if pool is not None:
        await pool.close()


async def check_pool(pool: PoolLike | None) -> bool:
    if pool is None:
        return False
    try:
        async with pool.acquire() as connection:
            value: Any = await connection.fetchval(
                "SELECT current_setting('transaction_read_only') = 'on'"
            )
        return bool(value)
    except Exception:
        return False
