from unihub_insight_api.repositories.base import AnalyticsRepository
from unihub_insight_api.repositories.demo import DemoAnalyticsRepository
from unihub_insight_api.repositories.demo_modules import DemoInsightRepository
from unihub_insight_api.repositories.postgres_modules import PostgresInsightRepository

__all__ = [
    "AnalyticsRepository",
    "DemoAnalyticsRepository",
    "DemoInsightRepository",
    "PostgresInsightRepository",
]
