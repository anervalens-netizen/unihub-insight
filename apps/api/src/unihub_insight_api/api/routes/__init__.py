from unihub_insight_api.api.routes.analytics import router as analytics_router
from unihub_insight_api.api.routes.auth import router as auth_router
from unihub_insight_api.api.routes.dashboards import router as dashboards_router
from unihub_insight_api.api.routes.health import router as health_router

__all__ = ["analytics_router", "auth_router", "dashboards_router", "health_router"]
