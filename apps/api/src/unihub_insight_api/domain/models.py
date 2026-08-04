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


class Capability(StrEnum):
    ANALYTICS = "insight:analytics"
    MANAGEMENT = "insight:management"
    HR = "insight:hr"
    PNL = "insight:pnl"
    ADMIN = "insight:admin"


class ModuleId(StrEnum):
    SALES = "sales"
    PERFORMANCE = "performance"
    CAMPAIGNS = "campaigns"
    WORKFORCE = "workforce"
    COMPENSATION = "compensation"
    FINANCE = "finance"
    PLANNING = "planning"


class ChartKind(StrEnum):
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    STACKED_BAR = "stacked-bar"
    DONUT = "donut"
    HEATMAP = "heatmap"
    SCATTER = "scatter"
    WATERFALL = "waterfall"
    TABLE = "table"
    KPI = "kpi"


class FilterMode(StrEnum):
    INHERIT = "inherit"
    AUGMENT = "augment"
    OVERRIDE = "override"
    IGNORE = "ignore"


class DashboardVisibility(StrEnum):
    PRIVATE = "private"
    SHARED = "shared"


class AnalyticsScope(BaseModel):
    model_config = ConfigDict(frozen=True)

    period: str
    comparison: ComparisonMode = ComparisonMode.PREVIOUS_YEAR
    firm: str | None = None
    regional: str | None = None
    asm: str | None = None
    stores: tuple[str, ...] = ()
    agent: str | None = None


class UserContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: str
    email: str | None = None
    name: str | None = None
    groups: tuple[str, ...] = ()
    capabilities: frozenset[Capability]
    is_demo: bool = False


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
    required_capability: Capability = Capability.ANALYTICS


class ValueAxis(BaseModel):
    key: str
    label: str
    unit: MetricUnit


class TrendPoint(BaseModel):
    key: str
    label: str
    primary: Decimal | None
    comparison: Decimal | None = None
    target: Decimal | None = None
    secondary: Decimal | None = None
    is_estimate: bool = False


class BreakdownRow(BaseModel):
    id: str
    label: str
    context: str
    primary: Decimal
    secondary: Decimal | None = None
    tertiary: Decimal | None = None
    progress_pct: Decimal | None = None
    delta_pct: Decimal | None = None
    risk: RiskLevel = RiskLevel.HEALTHY


class MatrixCell(BaseModel):
    x: str
    y: str
    value: Decimal
    label: str | None = None
    risk: RiskLevel = RiskLevel.HEALTHY


class ModuleAnalyticsResponse(BaseModel):
    meta: OverviewMeta
    module: ModuleId
    title: str
    description: str
    required_capability: Capability
    axes: tuple[ValueAxis, ...]
    supported_charts: tuple[ChartKind, ...]
    kpis: list[KpiMetric]
    trend: list[TrendPoint]
    distribution: list[DimensionShare]
    breakdown: list[BreakdownRow]
    matrix: list[MatrixCell]
    alerts: list[InsightAlert]


class DashboardLayout(BaseModel):
    x: int = Field(ge=0, le=23)
    y: int = Field(ge=0)
    w: int = Field(ge=2, le=24)
    h: int = Field(ge=2, le=40)
    min_w: int = Field(default=2, ge=2, le=24)
    min_h: int = Field(default=2, ge=2, le=40)


class DashboardWidget(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    module: ModuleId
    title: str = Field(min_length=1, max_length=160)
    metric_id: str = Field(min_length=1, max_length=160)
    visualization: ChartKind
    dimension: str | None = Field(default=None, max_length=100)
    time_grain: str = Field(default="month", max_length=40)
    filter_mode: FilterMode = FilterMode.INHERIT
    filters: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str | int | float | bool] = Field(default_factory=dict)
    layout: DashboardLayout


class DashboardCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=600)
    visibility: DashboardVisibility = DashboardVisibility.PRIVATE
    widgets: list[DashboardWidget] = Field(default_factory=list, max_length=80)


class DashboardUpdateRequest(DashboardCreateRequest):
    version: int = Field(ge=1)


class DashboardDocument(BaseModel):
    id: str
    name: str
    description: str
    owner_subject: str
    visibility: DashboardVisibility
    version: int
    widgets: list[DashboardWidget]
    created_at: datetime
    updated_at: datetime


class DashboardListResponse(BaseModel):
    items: list[DashboardDocument]
