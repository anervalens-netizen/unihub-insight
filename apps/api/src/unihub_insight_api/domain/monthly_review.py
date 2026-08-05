from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from unihub_insight_api.domain.models import (
    InsightAlert,
    MetricUnit,
    OverviewMeta,
)


class ReviewStatus(StrEnum):
    OUTPERFORMING = "outperforming"
    HEALTHY = "healthy"
    WATCH = "watch"
    RISK = "risk"
    RECOVERING = "recovering"
    SLOWING = "slowing"
    VOLATILE = "volatile"
    NEW = "new"
    EXITED = "exited"


class DeltaKind(StrEnum):
    PERCENT = "percent"
    PERCENTAGE_POINTS = "percentage-points"


class ComparisonMetric(BaseModel):
    id: str
    label: str
    unit: MetricUnit
    current: Decimal
    previous_year: Decimal | None = None
    previous_month: Decimal | None = None
    recent_average: Decimal | None = None
    target: Decimal | None = None
    yoy_delta: Decimal | None = None
    mom_delta: Decimal | None = None
    recent_delta: Decimal | None = None
    target_delta: Decimal | None = None
    delta_kind: DeltaKind = DeltaKind.PERCENT


class MonthlyTrendPoint(BaseModel):
    period: str
    sales: Decimal
    units: Decimal
    receipts: Decimal
    target: Decimal
    target_pct: Decimal | None = None
    average_receipt: Decimal | None = None
    return_rate_pct: Decimal | None = None


class SeasonalityPoint(BaseModel):
    year: int
    previous_period: str
    current_period: str
    sales_lift_pct: Decimal | None = None
    units_lift_pct: Decimal | None = None
    receipts_lift_pct: Decimal | None = None
    sales_per_store_day_lift_pct: Decimal | None = None
    store_count: int
    is_current: bool = False


class DriverBridge(BaseModel):
    basis: str
    baseline_sales: Decimal
    current_sales: Decimal
    sales_difference: Decimal
    receipts_effect: Decimal
    units_per_receipt_effect: Decimal
    value_per_unit_effect: Decimal


class PerformanceReviewRow(BaseModel):
    id: str
    label: str
    context: str
    entity_type: str
    sales: Decimal
    units: Decimal
    receipts: Decimal
    target: Decimal | None = None
    target_pct: Decimal | None = None
    previous_year_sales: Decimal | None = None
    previous_month_sales: Decimal | None = None
    recent_average_sales: Decimal | None = None
    yoy_pct: Decimal | None = None
    mom_pct: Decimal | None = None
    recent_pct: Decimal | None = None
    average_receipt: Decimal | None = None
    units_per_receipt: Decimal | None = None
    value_per_unit: Decimal | None = None
    bon2acc_pct: Decimal | None = None
    focus_pct: Decimal | None = None
    return_rate_pct: Decimal | None = None
    working_days: Decimal | None = None
    consistency_pct: Decimal | None = None
    performance_score: Decimal = Field(ge=0, le=100)
    status: ReviewStatus
    primary_driver: str
    primary_driver_impact: Decimal
    driver_basis: str


class ProductReviewRow(BaseModel):
    id: str
    label: str
    brand: str
    category: str
    sales: Decimal
    previous_year_sales: Decimal | None = None
    recent_average_sales: Decimal | None = None
    yoy_pct: Decimal | None = None
    recent_pct: Decimal | None = None
    units: Decimal
    previous_year_units: Decimal | None = None
    distribution: int | None = None
    previous_year_distribution: int | None = None
    return_rate_pct: Decimal | None = None
    previous_year_return_rate_pct: Decimal | None = None
    impact_yoy: Decimal
    impact_recent: Decimal
    score: Decimal
    status: ReviewStatus


class ReturnReviewRow(BaseModel):
    id: str
    label: str
    context: str
    entity_type: str
    current_value: Decimal
    previous_year_value: Decimal | None = None
    recent_average_value: Decimal | None = None
    current_rate_pct: Decimal | None = None
    previous_year_rate_pct: Decimal | None = None
    recent_rate_pct: Decimal | None = None
    yoy_rate_delta_pp: Decimal | None = None
    recent_rate_delta_pp: Decimal | None = None
    status: ReviewStatus


class MonthlyReviewResponse(BaseModel):
    meta: OverviewMeta
    recent_months: int = Field(ge=3, le=12)
    executive: list[ComparisonMetric]
    trend: list[MonthlyTrendPoint]
    seasonality: list[SeasonalityPoint]
    drivers: list[DriverBridge]
    companies: list[PerformanceReviewRow]
    managers: list[PerformanceReviewRow]
    stores: list[PerformanceReviewRow]
    categories: list[ProductReviewRow]
    products: list[ProductReviewRow]
    returns: list[ReturnReviewRow]
    agents: list[PerformanceReviewRow]
    alerts: list[InsightAlert]
    methodology: list[str]
