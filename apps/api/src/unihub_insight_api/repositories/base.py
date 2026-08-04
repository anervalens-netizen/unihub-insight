from __future__ import annotations

from typing import Protocol

from unihub_insight_api.domain import AnalyticsScope, FilterOptionsResponse, OverviewResponse


class AnalyticsRepository(Protocol):
    async def get_filter_options(self, period: str) -> FilterOptionsResponse: ...

    async def get_overview(self, scope: AnalyticsScope) -> OverviewResponse: ...
