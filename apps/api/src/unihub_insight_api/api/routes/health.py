from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, Response, status

from unihub_insight_api.config import Settings
from unihub_insight_api.db import check_pool

router = APIRouter(tags=["health"])


@router.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    ready, data_mode = await _readiness(request)
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A required PostgreSQL dependency is unavailable.",
        )
    return {"status": "ready", "data_mode": data_mode}


async def _readiness(request: Request) -> tuple[bool, str]:
    settings = cast(Settings, request.app.state.settings)
    if settings.data_mode == "demo":
        return True, "demo"

    if not await check_pool(getattr(request.app.state, "pool", None), expect_read_only=True):
        return False, "postgres"
    metadata_pool = getattr(request.app.state, "metadata_pool", None)
    if metadata_pool is not None and not await check_pool(metadata_pool, expect_read_only=False):
        return False, "postgres"
    return True, "postgres"


@router.get("/ready-metrics", include_in_schema=False)
async def readiness_metrics(request: Request) -> Response:
    ready, _data_mode = await _readiness(request)
    value = 1 if ready else 0
    return Response(
        content=(
            "# HELP unihub_insight_ready Whether required Insight dependencies are ready.\n"
            "# TYPE unihub_insight_ready gauge\n"
            f"unihub_insight_ready {value}\n"
        ),
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
