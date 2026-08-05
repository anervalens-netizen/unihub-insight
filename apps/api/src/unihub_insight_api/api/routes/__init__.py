from unihub_insight_api.api.routes.analytics import router as analytics_router
from unihub_insight_api.api.routes.auth import router as auth_router
from unihub_insight_api.api.routes.dashboards import router as dashboards_router
from unihub_insight_api.api.routes.exports import router as exports_router
from unihub_insight_api.api.routes.health import router as health_router
from unihub_insight_api.api.routes.monthly_review import router as monthly_review_router

__all__ = [
    "analytics_router",
    "auth_router",
    "dashboards_router",
    "exports_router",
    "health_router",
    "monthly_review_router",
]
