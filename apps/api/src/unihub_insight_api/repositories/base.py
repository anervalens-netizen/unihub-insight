from __future__ import annotations

from typing import Protocol

from unihub_insight_api.domain import (
    AnalyticalSnapshot,
    AnalyticsScope,
    FilterOptionsResponse,
    ModuleAnalyticsResponse,
    ModuleId,
    MonthlyReviewResponse,
    OverviewResponse,
)


class AnalyticsRepository(Protocol):
    async def resolve_snapshot(self, scope: AnalyticsScope) -> AnalyticalSnapshot: ...

    async def get_filter_options(self, period: str) -> FilterOptionsResponse: ...

    async def get_overview(self, scope: AnalyticsScope) -> OverviewResponse: ...

    async def get_module(
        self,
        module: ModuleId,
        scope: AnalyticsScope,
    ) -> ModuleAnalyticsResponse: ...

    async def get_monthly_review(
        self,
        scope: AnalyticsScope,
        recent_months: int,
    ) -> MonthlyReviewResponse: ...
