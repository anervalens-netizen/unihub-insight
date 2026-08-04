from __future__ import annotations

import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from unihub_insight_api.api.routes import analytics_router, auth_router, dashboards_router, health_router
from unihub_insight_api.config import Settings, get_settings
from unihub_insight_api.db import close_pool, create_metadata_pool, create_pool
from unihub_insight_api.repositories.dashboards import MemoryDashboardStore, PostgresDashboardStore
from unihub_insight_api.repositories.demo_modules import DemoInsightRepository
from unihub_insight_api.repositories.postgres_modules import PostgresInsightRepository


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _request_id(value: str | None) -> str:
    if value and REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return uuid.uuid4().hex


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.pool = None
        app.state.metadata_pool = None
        if resolved_settings.data_mode == "postgres":
            app.state.pool = await create_pool(resolved_settings)
            app.state.analytics_repository = PostgresInsightRepository(app.state.pool)
        else:
            app.state.analytics_repository = DemoInsightRepository()
        if resolved_settings.metadata_database_url:
            app.state.metadata_pool = await create_metadata_pool(resolved_settings)
            app.state.dashboard_store = PostgresDashboardStore(app.state.metadata_pool)
        else:
            app.state.dashboard_store = MemoryDashboardStore()
        try:
            yield
        finally:
            await close_pool(app.state.metadata_pool)
            await close_pool(app.state.pool)

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if resolved_settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if resolved_settings.environment != "production" else None,
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Server-Timing"],
    )

    @app.middleware("http")
    async def request_metadata(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.2f}"
        response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": resolved_settings.app_name,
            "version": resolved_settings.version,
            "data_mode": resolved_settings.data_mode,
            "auth_mode": resolved_settings.auth_mode,
        }

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(analytics_router)
    app.include_router(dashboards_router)
    return app


app = create_app()
