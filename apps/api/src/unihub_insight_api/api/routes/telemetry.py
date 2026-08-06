from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field

from unihub_insight_api.api.dependencies import AnalyticsUserDependency
from unihub_insight_api.observability import metrics, traffic_class

router = APIRouter(tags=["telemetry"])


class WebVitalPayload(BaseModel):
    metric: Literal["LCP", "INP"]
    value_ms: float = Field(ge=0, le=120_000)
    rating: Literal["good", "needs-improvement", "poor"]
    navigation_type: Literal[
        "navigate",
        "reload",
        "back-forward",
        "back-forward-cache",
        "prerender",
        "restore",
        "unknown",
    ] = "unknown"
    surface: Literal[
        "overview",
        "monthly-review",
        "module-sales",
        "module-performance",
        "module-campaigns",
        "module-workforce",
        "module-compensation",
        "module-finance",
        "module-planning",
        "custom-dashboards",
        "other",
    ] = "other"


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    return Response(
        content=metrics.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/api/v1/telemetry/web-vital",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def web_vital(
    payload: WebVitalPayload,
    user: AnalyticsUserDependency,
    request: Request,
) -> Response:
    metrics.record_web_vital(
        source_sha=request.app.state.source_sha,
        traffic_class=traffic_class(subject=user.subject, demo=user.is_demo),
        surface=payload.surface,
        metric=payload.metric,
        rating=payload.rating,
        navigation_type=payload.navigation_type,
        value_ms=payload.value_ms,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
