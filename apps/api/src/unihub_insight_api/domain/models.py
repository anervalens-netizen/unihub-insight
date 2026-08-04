from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ComparisonMode(StrEnum):
    PREVIOUS_MONTH = "previous-month"
    PREVIOUS_YEAR = "previous-year"
    NONE = "none"


class DataMode(StrEnum):
    DEMO = "demo"
    POSTGRES = "postgres"


class RiskLevel(StrEnum):
    HEALTHY = "healthy"
    WATCH = "watch"
    RISK = "risk"


class MetricUnit(StrEnum):
    CURRENCY = "currency"
    PERCENT = "percent"
    INTEGER = "integer"
    DECIMAL = "decimal"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AnalyticsScope(BaseModel):
    model_config = ConfigDict(frozen=True)

    period: str
    comparison: ComparisonMode = ComparisonMode.PREVIOUS_YEAR
    firm: str | None = None
    regional: str | None = None
    asm: str | None = None
    stores: tuple[str, ...] = ()
    agent: str | None = None


class FilterStore(BaseModel):
    site_code: str
    label: str
    firm: str
    regional: str
    asm: str | None = None


class FilterAgent(BaseModel):
    name: str
    site_code: str
    firm: str
    regional: str
    asm: str | None = None


class FilterOptionsResponse(BaseModel):
    periods: list[str]
    firms: list[str]
    regionals: list[str]
    asms: list[str]
    stores: list[FilterStore]
    agents: list[FilterAgent]
    data_mode: DataMode


class OverviewMeta(BaseModel):
    period: str
    comparison: ComparisonMode
    as_of: date | None
    is_final: bool
    data_mode: DataMode
    currency: str = "RON"
    scope_label: str
    generated_at: datetime
    source: str


class KpiMetric(BaseModel):
    id: str
    label: str
    value: Decimal
    unit: MetricUnit
    delta_pct: Decimal | None = None
    delta_label: str | None = None
    risk: RiskLevel = RiskLevel.HEALTHY
    supporting_value: Decimal | None = None
    supporting_label: str | None = None


class DailyPoint(BaseModel):
    day: int = Field(ge=1, le=31)
    sales: Decimal | None
    target_pace: Decimal
    forecast: Decimal | None = None
    comparison: Decimal | None = None


class DimensionShare(BaseModel):
    id: str
    label: str
    value: Decimal
    share_pct: Decimal


class PerformanceRow(BaseModel):
    id: str
    label: str
    context: str
    sales: Decimal
    target: Decimal
    progress_pct: Decimal | None
    delta_pct: Decimal | None = None
    risk: RiskLevel


class InsightAlert(BaseModel):
    id: str
    severity: AlertSeverity
    title: str
    description: str
    entity_label: str | None = None


class OverviewResponse(BaseModel):
    meta: OverviewMeta
    kpis: list[KpiMetric]
    daily: list[DailyPoint]
    contribution: list[DimensionShare]
    performance: list[PerformanceRow]
    alerts: list[InsightAlert]


class MetricDefinition(BaseModel):
    id: str
    version: int = 1
    display_name: str
    description: str
    unit: MetricUnit
    aggregation: str
    allowed_dimensions: tuple[str, ...]
    allowed_grains: tuple[str, ...]
    comparison_policy: str
    missing_policy: str
    required_capability: str = "insight:analytics"
