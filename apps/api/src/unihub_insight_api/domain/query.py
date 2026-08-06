from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from unihub_insight_api.domain.models import (
    ChartKind,
    ModuleId,
    SourceMetadata,
)


class QueryComparison(StrEnum):
    TARGET = "target"
    FORECAST = "forecast"
    PREVIOUS_PERIOD = "previous-period"
    PREVIOUS_YEAR = "previous-year"
    RECENT_AVERAGE = "recent-average"


class QuerySortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class QueryErrorCode(StrEnum):
    INVALID_QUERY = "invalid-query"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    DEADLINE_EXCEEDED = "deadline-exceeded"
    INTERNAL = "internal"


FilterValue = str | tuple[str, ...]
DatasetValue = str | Decimal | int | bool | None


class QueryTimeRange(BaseModel):
    start: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    end: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    @model_validator(mode="after")
    def validate_order(self) -> QueryTimeRange:
        if self.start > self.end:
            raise ValueError("time_range.start cannot be after time_range.end")
        return self


class QuerySort(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    direction: QuerySortDirection = QuerySortDirection.DESC


class WidgetQuery(BaseModel):
    widget_id: str = Field(min_length=1, max_length=100)
    module: ModuleId
    metric_id: str = Field(min_length=1, max_length=160)
    metric_version: int = Field(default=1, ge=1)
    query_contract_version: int = Field(default=1, ge=1)
    dimensions: tuple[str, ...] = Field(default=(), max_length=2)
    time_range: QueryTimeRange | None = None
    time_grain: str = Field(default="month", pattern=r"^(day|week|month|quarter|year)$")
    filters: dict[str, FilterValue] = Field(default_factory=dict)
    comparisons: tuple[QueryComparison, ...] = ()
    sort: tuple[QuerySort, ...] = ()
    limit: int = Field(default=30, ge=1, le=5000)
    visualization: ChartKind = ChartKind.TABLE

    @field_validator("dimensions")
    @classmethod
    def unique_dimensions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("dimensions must be unique")
        return value


class QueryBatchRequest(BaseModel):
    snapshot_id: str | None = Field(default=None, max_length=160)
    dashboard_id: str | None = Field(default=None, max_length=100)
    widgets: list[WidgetQuery] = Field(min_length=1, max_length=12)

    @field_validator("widgets")
    @classmethod
    def unique_widget_ids(cls, value: list[WidgetQuery]) -> list[WidgetQuery]:
        identifiers = [widget.widget_id for widget in value]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("widget_id must be unique within a batch")
        return value


class AnalyticalSnapshot(BaseModel):
    id: str
    contract_version: int = 1
    period: str
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sources: dict[str, SourceMetadata]


class DatasetDimension(BaseModel):
    id: str
    label: str
    kind: str = Field(pattern=r"^(string|number|integer|boolean|time)$")
    role: str = Field(default="value", pattern=r"^(key|label|value|comparison|target|metadata)$")


class QueryDataset(BaseModel):
    dimensions: list[DatasetDimension]
    rows: list[dict[str, DatasetValue]]


class QueryExecutionMeta(BaseModel):
    period: str
    scope_label: str
    snapshot_id: str
    source: SourceMetadata
    sources: dict[str, SourceMetadata] = Field(default_factory=dict)
    metric_id: str
    metric_version: int
    query_contract_version: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    warnings: tuple[str, ...] = ()


class QueryError(BaseModel):
    code: QueryErrorCode
    message: str
    retryable: bool = False


class WidgetQueryResult(BaseModel):
    widget_id: str
    query: WidgetQuery
    dataset: QueryDataset | None = None
    meta: QueryExecutionMeta | None = None
    error: QueryError | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> WidgetQueryResult:
        if (self.dataset is None) == (self.error is None):
            raise ValueError("exactly one of dataset or error is required")
        return self


class QueryBatchResponse(BaseModel):
    snapshot: AnalyticalSnapshot
    results: list[WidgetQueryResult]
    deadline_ms: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InspectRequest(BaseModel):
    snapshot_id: str
    dashboard_id: str | None = None
    query: WidgetQuery
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=500)


class InspectResponse(BaseModel):
    snapshot: AnalyticalSnapshot
    query: WidgetQuery
    dataset: QueryDataset
    page: int
    page_size: int
    total_rows: int
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
