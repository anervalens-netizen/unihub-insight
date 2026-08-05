from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from unihub_insight_api.config import Settings
from unihub_insight_api.db import check_pool

router = APIRouter(tags=["health"])


@router.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    settings = cast(Settings, request.app.state.settings)
    if settings.data_mode == "demo":
        return {"status": "ready", "data_mode": "demo"}

    if not await check_pool(getattr(request.app.state, "pool", None), expect_read_only=True):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PostgreSQL read-only dependency is unavailable.",
        )
    metadata_pool = getattr(request.app.state, "metadata_pool", None)
    if metadata_pool is not None and not await check_pool(metadata_pool, expect_read_only=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Insight metadata dependency is unavailable.",
        )
    return {"status": "ready", "data_mode": "postgres"}
