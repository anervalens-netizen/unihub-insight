from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal

from unihub_insight_api.domain import (
    AnalyticsScope,
    Capability,
    ChartKind,
    ComparisonMode,
    DatasetDimension,
    MetricDefinition,
    ModuleAnalyticsResponse,
    ModuleAnalyticsSlice,
    ModuleId,
    QueryBatchRequest,
    QueryBatchResponse,
    QueryComparison,
    QueryDataset,
    QueryError,
    QueryErrorCode,
    QueryExecutionMeta,
    QuerySort,
    SourceDomain,
    SourceStatus,
    UserContext,
    WidgetQuery,
    WidgetQueryResult,
)
from unihub_insight_api.repositories.base import AnalyticsRepository
from unihub_insight_api.services.metric_catalog import (
    METRIC_CATALOG,
    PORTFOLIO_DIMENSIONS,
    PORTFOLIO_METRIC_IDS,
    metric_entity_dimension,
)
from unihub_insight_api.services.scope import scope_label

ALLOWED_FILTERS = frozenset({"firm", "regional", "asm", "stores", "agent"})
ALLOWED_SORT_FIELDS = frozenset(
    {
        "id",
        "key",
        "date",
        "label",
        "value",
        "comparison",
        "target",
        "secondary",
        "tertiary",
        "quaternary",
        "progress_pct",
        "risk",
        "net_quantity",
        "return_quantity",
        "receipt_count",
    }
)
METRICS = {metric.id: metric for metric in METRIC_CATALOG}
COMMERCIAL_CAMPAIGN_METRICS = frozenset(
    metric_id
    for metric_id in METRICS
    if metric_id.startswith("campaigns.promo_") or metric_id.startswith("campaigns.incentive_")
)
VISIT_METRICS = frozenset(
    {
        "visits.total",
        "visits.distinct_stores",
        "visits.avg_completion",
        "visits.checklist_score",
    }
)
MODULE_METRICS: dict[ModuleId, frozenset[str]] = {
    ModuleId.SALES: frozenset(
        {
            "sales.total",
            "target.progress_pct",
            "receipts.total",
            "receipts.average_value",
            "receipt_2plus_pct",
            *PORTFOLIO_METRIC_IDS,
        }
    ),
    ModuleId.PERFORMANCE: frozenset(
        {
            "performance.average",
            "performance.at_target",
            "performance.volatility",
            "performance.daily_productivity",
            *VISIT_METRICS,
        }
    ),
    ModuleId.CAMPAIGNS: frozenset(
        {
            "campaigns.focus_sales",
            "campaigns.focus_share",
            "campaigns.active_stores",
            "campaigns.active_products",
            *COMMERCIAL_CAMPAIGN_METRICS,
        }
    ),
    ModuleId.WORKFORCE: frozenset(
        {
            "workforce.headcount",
            "workforce.productivity",
            "workforce.coverage",
            "workforce.stability",
            *VISIT_METRICS,
        }
    ),
    ModuleId.COMPENSATION: frozenset(
        {"compensation.payroll", "compensation.average", "compensation.median", "compensation.sales_ratio"}
    ),
    ModuleId.FINANCE: frozenset({"finance.revenue", "finance.ebit", "finance.ebit_margin", "finance.operating_costs"}),
    ModuleId.PLANNING: frozenset({"planning.forecast", "planning.target_gap", "planning.accuracy", "planning.actual"}),
}
MODULE_SOURCE_DOMAINS: dict[ModuleId, SourceDomain] = {
    ModuleId.SALES: SourceDomain.SALES,
    ModuleId.PERFORMANCE: SourceDomain.SALES,
    ModuleId.CAMPAIGNS: SourceDomain.CAMPAIGNS,
    ModuleId.WORKFORCE: SourceDomain.WORKFORCE,
    ModuleId.COMPENSATION: SourceDomain.COMPENSATION,
    ModuleId.FINANCE: SourceDomain.FINANCE,
    ModuleId.PLANNING: SourceDomain.PLANNING,
}


def primary_source_domain(query: WidgetQuery) -> SourceDomain:
    return SourceDomain.VISITS if query.metric_id in VISIT_METRICS else MODULE_SOURCE_DOMAINS[query.module]


def required_source_domains(query: WidgetQuery) -> tuple[SourceDomain, ...]:
    primary = primary_source_domain(query)
    if query.metric_id in VISIT_METRICS:
        return (primary,)
    if query.module in {ModuleId.CAMPAIGNS, ModuleId.COMPENSATION, ModuleId.PLANNING}:
        return (primary, SourceDomain.SALES)
    return (primary,)


MODULE_CAPABILITIES: dict[ModuleId, Capability] = {
    ModuleId.SALES: Capability.ANALYTICS,
    ModuleId.PERFORMANCE: Capability.ANALYTICS,
    ModuleId.CAMPAIGNS: Capability.ANALYTICS,
    ModuleId.WORKFORCE: Capability.MANAGEMENT,
    ModuleId.COMPENSATION: Capability.HR,
    ModuleId.FINANCE: Capability.PNL,
    ModuleId.PLANNING: Capability.MANAGEMENT,
}
SCALAR_ONLY_METRICS = frozenset(
    {
        "receipts.total",
        "receipts.average_value",
        "receipt_2plus_pct",
        "performance.at_target",
        "performance.volatility",
        "campaigns.active_stores",
        "campaigns.active_products",
        "campaigns.promo_active_stores",
        "campaigns.promo_active_products",
        "campaigns.incentive_active_stores",
        "campaigns.incentive_active_products",
        "workforce.coverage",
        "workforce.stability",
        "compensation.sales_ratio",
        "planning.accuracy",
        "visits.distinct_stores",
    }
)


@dataclass(frozen=True)
class QueryValidationFailure(ValueError):
    message: str


@dataclass(frozen=True)
class SnapshotConflictError(RuntimeError):
    requested: str
    current: str


def _metric_for(query: WidgetQuery, user: UserContext) -> MetricDefinition:
    metric = METRICS.get(query.metric_id)
    if metric is None or metric.version != query.metric_version:
        raise QueryValidationFailure(f"Metrica {query.metric_id} v{query.metric_version} nu este în catalogul activ.")
    if query.metric_id not in MODULE_METRICS[query.module]:
        raise QueryValidationFailure(f"Metrica {query.metric_id} nu aparține modulului {query.module.value}.")
    required = MODULE_CAPABILITIES[query.module]
    if required not in user.capabilities or metric.required_capability not in user.capabilities:
        raise PermissionError(f"Capability {required.value} este necesară.")
    unknown_filters = set(query.filters) - ALLOWED_FILTERS
    if unknown_filters:
        raise QueryValidationFailure(f"Filtre neacceptate: {', '.join(sorted(unknown_filters))}.")
    unknown_sort = {item.field for item in query.sort} - ALLOWED_SORT_FIELDS
    if unknown_sort:
        raise QueryValidationFailure(f"Sortări neacceptate: {', '.join(sorted(unknown_sort))}.")
    unknown_comparisons = {comparison.value for comparison in query.comparisons} - set(metric.allowed_comparisons)
    if unknown_comparisons:
        raise QueryValidationFailure(
            f"Comparații neacceptate pentru metrică: {', '.join(sorted(unknown_comparisons))}."
        )
    if query.comparisons and "time" not in query.dimensions:
        raise QueryValidationFailure("Comparațiile cer dimensiunea time.")
    if any(dimension not in metric.allowed_dimensions for dimension in query.dimensions):
        raise QueryValidationFailure("Combinația metrică × dimensiune nu este permisă.")
    if query.metric_id in PORTFOLIO_METRIC_IDS and (
        len(query.dimensions) != 1 or query.dimensions[0] not in PORTFOLIO_DIMENSIONS
    ):
        raise QueryValidationFailure(
            "Portofoliul Sales cere exact o dimensiune: category, subcategory, brand sau product."
        )
    if (
        query.metric_id in PORTFOLIO_METRIC_IDS
        and query.dimensions == ("product",)
        and query.visualization not in {ChartKind.KPI, ChartKind.TABLE}
    ):
        raise QueryValidationFailure(
            "Produsele acceptă numai KPI și tabel; distribuțiile cu sute de SKU nu sunt eligibile."
        )
    if query.time_grain not in metric.allowed_grains:
        raise QueryValidationFailure("Granularitatea nu este permisă pentru metrică.")
    if query.visualization not in metric.allowed_shapes:
        raise QueryValidationFailure("Vizualizarea nu este permisă de ChartSpec-ul metricii.")
    if query.metric_id in SCALAR_ONLY_METRICS and query.dimensions:
        raise QueryValidationFailure("Metrica este disponibilă numai ca agregat fără dimensiuni.")
    if query.visualization in {ChartKind.LINE, ChartKind.AREA} and query.dimensions != ("time",):
        raise QueryValidationFailure("Trendul cere exact dimensiunea time.")
    distribution_dimensions = {
        "sales.total": "category",
        "campaigns.focus_sales": "category",
        "campaigns.promo_sales": "category",
        "campaigns.promo_discount": "category",
        "campaigns.incentive_sales": "category",
        "campaigns.incentive_reward": "category",
        "workforce.headcount": "tenure",
        "compensation.payroll": "firm",
        "finance.operating_costs": "category",
    }
    if query.visualization in {ChartKind.DONUT, ChartKind.TREEMAP}:
        if query.metric_id in PORTFOLIO_METRIC_IDS:
            if len(query.dimensions) != 1 or query.dimensions[0] not in metric.allowed_dimensions:
                raise QueryValidationFailure("Mixul de portofoliu cere dimensiunea taxonomică a metricii.")
        elif query.dimensions != (distribution_dimensions.get(query.metric_id),):
            raise QueryValidationFailure("Mixul cere dimensiunea agregată aprobată pentru metrică.")
    if query.visualization is ChartKind.WATERFALL and (
        query.metric_id != "finance.ebit" or query.dimensions != ("category",)
    ):
        raise QueryValidationFailure("Waterfall cere reconcilierea Finance EBIT pe category.")
    if query.visualization is ChartKind.CALENDAR and (
        query.module is not ModuleId.SALES
        or query.metric_id != "sales.total"
        or query.dimensions != ("time",)
        or query.time_grain != "day"
    ):
        raise QueryValidationFailure("Calendar cere sales.total × time la granularitate day.")
    if len(query.dimensions) > 1 and query.visualization is not ChartKind.HEATMAP:
        raise QueryValidationFailure("Două dimensiuni sunt suportate numai de heatmap.")
    if query.visualization is ChartKind.HEATMAP and query.dimensions != (
        metric_entity_dimension(query.module, query.metric_id),
        "time",
    ):
        raise QueryValidationFailure("Heatmap cere exact dimensiunile entitate × time ale modulului.")
    if query.visualization in {ChartKind.HISTOGRAM, ChartKind.BOXPLOT, ChartKind.SCATTER} and (
        not query.dimensions or "time" in query.dimensions
    ):
        raise QueryValidationFailure("Distribuția/relația cere o dimensiune de entitate, nu time.")
    if query.module is ModuleId.COMPENSATION and (
        set(query.filters) - {"firm"} or set(query.dimensions) - {"firm", "time"}
    ):
        raise QueryValidationFailure("Compensation permite numai partiții agregate aprobate pe companie și timp.")
    if query.module in {ModuleId.FINANCE, ModuleId.PLANNING} and "agent" in query.filters:
        raise QueryValidationFailure(f"Filtrul agent nu este permis pentru {query.module.value}.")
    if query.metric_id in VISIT_METRICS and "agent" in query.filters:
        raise QueryValidationFailure("Filtrul agent nu este permis pentru vizitele atribuite Team Leader-ului autor.")
    return metric


def _filter_text(value: str | tuple[str, ...] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, tuple):
        return value[0] if value else None
    return value.strip() or None


def _filter_values(value: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    source = value.split(",") if isinstance(value, str) else value
    return tuple(dict.fromkeys(item.strip() for item in source if item.strip()))


def resolve_query_scope(base: AnalyticsScope, query: WidgetQuery) -> AnalyticsScope:
    filters = query.filters
    stores_value = filters.get("stores", base.stores)
    if isinstance(stores_value, str):
        stores = tuple(dict.fromkeys(item.strip() for item in stores_value.split(",") if item.strip()))
    else:
        stores = tuple(stores_value)
    period = query.time_range.end if query.time_range else base.period
    return AnalyticsScope(
        period=period,
        comparison=base.comparison,
        firm=_filter_text(filters.get("firm", base.firm)),
        regional=_filter_values(filters.get("regional", base.regional)),
        asm=_filter_text(filters.get("asm", base.asm)),
        stores=stores,
        agent=_filter_values(filters.get("agent", base.agent)),
    )


def comparison_scopes(scope: AnalyticsScope, query: WidgetQuery) -> dict[QueryComparison, AnalyticsScope]:
    modes = {
        QueryComparison.PREVIOUS_PERIOD: ComparisonMode.PREVIOUS_MONTH,
        QueryComparison.PREVIOUS_YEAR: ComparisonMode.PREVIOUS_YEAR,
    }
    return {
        comparison: scope.model_copy(update={"comparison": modes[comparison]})
        for comparison in query.comparisons
        if comparison in modes
    }


def _sorted_rows(
    rows: list[dict[str, str | Decimal | int | bool | None]],
    sort: tuple[QuerySort, ...],
    limit: int,
) -> list[dict[str, str | Decimal | int | bool | None]]:
    ordered = list(rows)
    for rule in reversed(sort):
        present = [row for row in ordered if row.get(rule.field) is not None]
        missing = [row for row in ordered if row.get(rule.field) is None]
        reverse = rule.direction.value == "desc"
        if all(isinstance(row.get(rule.field), (Decimal, int)) for row in present):
            present.sort(key=lambda row: Decimal(str(row[rule.field])), reverse=reverse)
        else:
            present.sort(key=lambda row: str(row[rule.field]), reverse=reverse)
        ordered = [*present, *missing]
    return ordered[:limit]


def _field_for(module: ModuleId, metric_id: str, *, breakdown: bool = False) -> str:
    mappings: dict[str, str] = {
        "sales.total": "primary",
        "sales.portfolio_sales": "primary",
        "sales.portfolio_net_quantity": "secondary",
        "sales.portfolio_return_quantity": "tertiary",
        "sales.portfolio_receipt_incidence": "quaternary",
        "target.progress_pct": "progress_pct" if breakdown else "primary",
        "performance.average": "progress_pct" if breakdown else "primary",
        "performance.daily_productivity": "tertiary" if breakdown else "secondary",
        "campaigns.focus_sales": "primary",
        "campaigns.focus_share": "progress_pct" if breakdown else "secondary",
        "campaigns.promo_sales": "primary",
        "campaigns.promo_quantity": "secondary",
        "campaigns.promo_discount": "tertiary" if breakdown else "secondary",
        "campaigns.incentive_sales": "primary",
        "campaigns.incentive_quantity": "secondary",
        "campaigns.incentive_reward": "tertiary" if breakdown else "secondary",
        "workforce.headcount": "primary",
        "workforce.productivity": "secondary",
        "workforce.stability": "comparison" if not breakdown else "progress_pct",
        "compensation.payroll": "primary",
        "compensation.average": "secondary",
        "compensation.median": "tertiary" if breakdown else "comparison",
        "finance.revenue": "primary",
        "finance.ebit": "secondary",
        "finance.ebit_margin": "target" if not breakdown else "progress_pct",
        "finance.operating_costs": "tertiary" if breakdown else "primary",
        "planning.forecast": "primary",
        "planning.actual": "comparison" if not breakdown else "secondary",
        "planning.target_gap": "primary",
        "planning.accuracy": "progress_pct" if breakdown else "primary",
        "visits.total": "primary",
        "visits.distinct_stores": "tertiary" if breakdown else "primary",
        "visits.avg_completion": "secondary",
        "visits.checklist_score": "progress_pct" if breakdown else "primary",
    }
    return mappings.get(metric_id, "primary")


def _decimal_or_none(value: object) -> Decimal | int | str | bool | None:
    if value is None or isinstance(value, (Decimal, int, str, bool)):
        return value
    return Decimal(str(value))


def _data_for_metric(
    response: ModuleAnalyticsResponse,
    metric_id: str,
    dimensions: tuple[str, ...] = (),
) -> ModuleAnalyticsResponse | ModuleAnalyticsSlice:
    if metric_id in PORTFOLIO_METRIC_IDS:
        dimension = dimensions[0] if len(dimensions) == 1 else None
        data = response.portfolio.get(dimension or "")
        if data is None:
            raise RuntimeError("Portfolio analytics slice is unavailable.")
        return data
    if metric_id.startswith("campaigns.promo_"):
        data = response.campaigns.get("promo")
        if data is None:
            raise RuntimeError("Promo analytics slice is unavailable.")
        return data
    if metric_id.startswith("campaigns.incentive_"):
        data = response.campaigns.get("incentive")
        if data is None:
            raise RuntimeError("Incentive analytics slice is unavailable.")
        return data
    if metric_id not in VISIT_METRICS:
        return response
    if response.visits is None:
        raise RuntimeError("Visit analytics slice is unavailable.")
    return response.visits


def _dataset(
    query: WidgetQuery,
    response: ModuleAnalyticsResponse,
    comparison_responses: dict[QueryComparison, ModuleAnalyticsResponse] | None = None,
) -> QueryDataset:
    data = _data_for_metric(response, query.metric_id, query.dimensions)
    metric = next((item for item in data.kpis if item.id == query.metric_id), None)
    if query.visualization is ChartKind.KPI and query.metric_id == "target.progress_pct":
        actual = next((item for item in response.kpis if item.id == "sales.total"), None)
        target = metric.supporting_value if metric is not None else None
        actual_value = actual.value if actual is not None else None
        return QueryDataset(
            dimensions=[
                DatasetDimension(id="value", label="Realizare target", kind="number"),
                DatasetDimension(id="actual", label="Realizat", kind="number", role="metadata"),
                DatasetDimension(id="target", label="Target", kind="number", role="target"),
                DatasetDimension(id="gap", label="Gap", kind="number", role="metadata"),
            ],
            rows=[
                {
                    "value": metric.value if metric else None,
                    "actual": actual_value,
                    "target": target,
                    "gap": target - actual_value if target is not None and actual_value is not None else None,
                }
            ],
        )
    if query.visualization is ChartKind.KPI or not query.dimensions:
        return QueryDataset(
            dimensions=[DatasetDimension(id="value", label=metric.label if metric else query.metric_id, kind="number")],
            rows=[{"value": metric.value if metric else None}],
        )

    if query.visualization is ChartKind.WATERFALL:
        start_metric = next((item for item in data.kpis if item.id == "finance.revenue"), None)
        total_metric = next((item for item in data.kpis if item.id == "finance.ebit"), None)
        rows: list[dict[str, str | Decimal | int | bool | None]] = []
        if start_metric is not None and total_metric is not None:
            rows.append({"label": start_metric.label, "value": start_metric.value, "step_kind": "start"})
            rows.extend({"label": item.label, "value": -item.value, "step_kind": "delta"} for item in data.distribution)
            rows.append({"label": total_metric.label, "value": total_metric.value, "step_kind": "total"})
        return QueryDataset(
            dimensions=[
                DatasetDimension(id="label", label="Pas reconciliere", kind="string", role="label"),
                DatasetDimension(id="value", label=query.metric_id, kind="number"),
                DatasetDimension(id="step_kind", label="Tip pas", kind="string", role="metadata"),
            ],
            rows=rows,
        )

    if query.visualization is ChartKind.SCATTER:
        axes: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
            "performance.average": (("tertiary", "Productivitate / zi-agent"), ("progress_pct", "Realizare target")),
            "compensation.average": (("tertiary", "Salariu median"), ("secondary", "Salariu mediu")),
            "planning.forecast": (("secondary", "Actual"), ("primary", "Forecast")),
        }
        axis = axes.get(query.metric_id)
        rows = []
        if axis is not None:
            (x_field, x_label), (y_field, y_label) = axis
            for item in data.breakdown:
                x_value = getattr(item, x_field, None)
                y_value = getattr(item, y_field, None)
                if x_value is not None and y_value is not None:
                    rows.append(
                        {"id": item.id, "label": item.label, "x": x_value, "y": y_value, "risk": item.risk.value}
                    )
        else:
            x_label = "X"
            y_label = "Y"
        return QueryDataset(
            dimensions=[
                DatasetDimension(
                    id="id",
                    label="Cheie",
                    kind="string",
                    role="key",
                    source_dimension=metric_entity_dimension(query.module, query.metric_id),
                ),
                DatasetDimension(id="label", label="Entitate", kind="string", role="label"),
                DatasetDimension(id="x", label=x_label, kind="number"),
                DatasetDimension(id="y", label=y_label, kind="number", role="metadata"),
                DatasetDimension(id="risk", label="Risc", kind="string", role="metadata"),
            ],
            rows=_sorted_rows(rows, query.sort, query.limit),
        )

    if query.visualization is ChartKind.HEATMAP:
        heatmap_rows: list[dict[str, str | Decimal | int | bool | None]] = [
            {"x": cell.x, "y": cell.y, "value": cell.value, "label": cell.label} for cell in data.matrix[: query.limit]
        ]
        return QueryDataset(
            dimensions=[
                DatasetDimension(id="x", label="Perioadă", kind="string", role="key", source_dimension="time"),
                DatasetDimension(
                    id="y",
                    label="Entitate",
                    kind="string",
                    role="label",
                    source_dimension=metric_entity_dimension(query.module, query.metric_id),
                ),
                DatasetDimension(id="value", label=query.metric_id, kind="number"),
                DatasetDimension(id="label", label="Context", kind="string", role="metadata"),
            ],
            rows=_sorted_rows(heatmap_rows, query.sort, query.limit),
        )

    if query.visualization is ChartKind.CALENDAR:
        calendar_rows: list[dict[str, str | Decimal | int | bool | None]] = [
            {
                "date": cell.date.isoformat(),
                "label": cell.date.isoformat(),
                "value": cell.sales,
                "net_quantity": cell.net_quantity,
                "positive_quantity": cell.positive_quantity,
                "return_quantity": cell.return_quantity,
                "receipt_count": cell.receipt_count,
                "receipt_2plus_count": cell.receipt_2plus_count,
                "observed_store_count": cell.observed_store_count,
                "coverage_state": cell.coverage_state,
            }
            for cell in data.calendar
            if query.time_range is None or query.time_range.start <= cell.date.strftime("%Y-%m") <= query.time_range.end
        ]
        return QueryDataset(
            dimensions=[
                DatasetDimension(id="date", label="Dată", kind="time", role="key", source_dimension="time"),
                DatasetDimension(id="label", label="Zi observată", kind="string", role="label"),
                DatasetDimension(id="value", label="Vânzări", kind="number"),
                DatasetDimension(id="net_quantity", label="Cantitate netă", kind="integer", role="metadata"),
                DatasetDimension(id="positive_quantity", label="Cantitate pozitivă", kind="integer", role="metadata"),
                DatasetDimension(id="return_quantity", label="Cantitate retur", kind="integer", role="metadata"),
                DatasetDimension(id="receipt_count", label="Bonuri", kind="integer", role="metadata"),
                DatasetDimension(id="receipt_2plus_count", label="Bonuri 2+", kind="integer", role="metadata"),
                DatasetDimension(
                    id="observed_store_count", label="Magazine observate", kind="integer", role="metadata"
                ),
                DatasetDimension(id="coverage_state", label="Coverage", kind="string", role="metadata"),
            ],
            rows=_sorted_rows(calendar_rows, query.sort, query.limit),
        )

    if "time" in query.dimensions or query.visualization in {ChartKind.LINE, ChartKind.AREA}:
        field = _field_for(query.module, query.metric_id)
        trend_rows: list[dict[str, str | Decimal | int | bool | None]] = []
        points = data.trend
        comparison_points = {
            comparison: {
                point.key: point
                for point in _data_for_metric(comparison_response, query.metric_id, query.dimensions).trend
            }
            for comparison, comparison_response in (comparison_responses or {}).items()
        }
        primary_values: list[Decimal | None] = []
        for point in points:
            value = getattr(point, field, None)
            if query.metric_id == "target.progress_pct":
                value = (
                    point.primary / point.target * Decimal("100")
                    if point.primary is not None and point.target is not None and point.target > 0
                    else None
                )
            if query.metric_id == "planning.target_gap":
                value = point.primary - point.target if point.primary is not None and point.target is not None else None
            primary_values.append(Decimal(str(value)) if value is not None else None)
            trend_row: dict[str, str | Decimal | int | bool | None] = {
                "key": point.key,
                "label": point.label,
                "value": _decimal_or_none(value),
                "is_estimate": point.is_estimate,
            }
            if QueryComparison.TARGET in query.comparisons:
                trend_row["target"] = point.target
            for comparison, dimension_id in (
                (QueryComparison.PREVIOUS_PERIOD, "previous_period"),
                (QueryComparison.PREVIOUS_YEAR, "previous_year"),
            ):
                if comparison in query.comparisons:
                    reference_point = comparison_points.get(comparison, {}).get(point.key)
                    trend_row[dimension_id] = reference_point.comparison if reference_point else None
            if QueryComparison.FORECAST in query.comparisons:
                trend_row["forecast"] = (
                    point.primary
                    if query.module is ModuleId.PLANNING and query.metric_id == "planning.actual"
                    else None
                )
            if query.module is ModuleId.PLANNING and query.metric_id == "planning.forecast":
                trend_row["actual"] = point.comparison
            trend_rows.append(trend_row)
        if QueryComparison.RECENT_AVERAGE in query.comparisons:
            for index, trend_row in enumerate(trend_rows):
                window = [value for value in primary_values[max(0, index - 3) : index] if value is not None]
                trend_row["recent_average"] = sum(window, Decimal(0)) / Decimal(len(window)) if window else None
        if query.time_range is not None:
            trend_rows = [
                row for row in trend_rows if query.time_range.start <= str(row["key"]) <= query.time_range.end
            ]
        dimensions = [
            DatasetDimension(id="key", label="Cheie", kind="string", role="key", source_dimension="time"),
            DatasetDimension(id="label", label="Perioadă", kind="string", role="label"),
            DatasetDimension(id="value", label=query.metric_id, kind="number"),
        ]
        comparison_dimensions = {
            QueryComparison.PREVIOUS_PERIOD: ("previous_period", "Perioada precedentă"),
            QueryComparison.PREVIOUS_YEAR: ("previous_year", "Anul trecut"),
            QueryComparison.RECENT_AVERAGE: ("recent_average", "Media ultimelor 3 perioade"),
            QueryComparison.FORECAST: ("forecast", "Forecast"),
        }
        dimensions.extend(
            DatasetDimension(id=identifier, label=label, kind="number", role="comparison")
            for comparison, (identifier, label) in comparison_dimensions.items()
            if comparison in query.comparisons
        )
        if QueryComparison.TARGET in query.comparisons:
            dimensions.append(DatasetDimension(id="target", label="Target", kind="number", role="target"))
        if query.module is ModuleId.PLANNING and query.metric_id == "planning.forecast":
            dimensions.append(DatasetDimension(id="actual", label="Actual", kind="number", role="comparison"))
        dimensions.append(DatasetDimension(id="is_estimate", label="Estimat", kind="boolean", role="metadata"))
        return QueryDataset(
            dimensions=dimensions,
            rows=_sorted_rows(trend_rows, query.sort, query.limit),
        )

    if query.visualization in {ChartKind.DONUT, ChartKind.TREEMAP} or (
        query.metric_id not in PORTFOLIO_METRIC_IDS and query.dimensions[0] in {"category", "mechanism"}
    ):
        return QueryDataset(
            dimensions=[
                DatasetDimension(
                    id="id",
                    label="Cheie",
                    kind="string",
                    role="key",
                    source_dimension=query.dimensions[0],
                ),
                DatasetDimension(id="label", label="Categorie", kind="string", role="label"),
                DatasetDimension(id="value", label=query.metric_id, kind="number"),
                DatasetDimension(id="share_pct", label="Pondere", kind="number", role="metadata"),
            ],
            rows=_sorted_rows(
                [item.model_dump() for item in data.distribution],
                query.sort,
                min(query.limit, 30),
            ),
        )

    field = _field_for(query.module, query.metric_id, breakdown=True)
    entity_dimension = (
        query.dimensions[0]
        if query.metric_id in PORTFOLIO_METRIC_IDS
        else metric_entity_dimension(query.module, query.metric_id)
    )
    breakdown_rows: list[dict[str, str | Decimal | int | bool | None]] = []
    for row in data.breakdown:
        value = _decimal_or_none(getattr(row, field, None))
        if query.metric_id == "workforce.headcount":
            value = 1
        elif query.metric_id == "planning.target_gap":
            value = row.primary - row.tertiary if row.tertiary is not None else None
        breakdown_rows.append(
            {
                "id": row.id,
                "label": row.label,
                "context": row.context,
                "value": value,
                "secondary": row.secondary,
                "tertiary": row.tertiary,
                "quaternary": row.quaternary,
                "progress_pct": row.progress_pct,
                "risk": row.risk.value,
            }
        )
    return QueryDataset(
        dimensions=[
            DatasetDimension(
                id="id",
                label="Cheie",
                kind="string",
                role="key",
                source_dimension=entity_dimension,
            ),
            DatasetDimension(id="label", label="Entitate", kind="string", role="label"),
            DatasetDimension(id="context", label="Context", kind="string", role="metadata"),
            DatasetDimension(id="value", label=query.metric_id, kind="number"),
            DatasetDimension(id="secondary", label="Secundar", kind="number", role="metadata"),
            DatasetDimension(id="tertiary", label="Terțiar", kind="number", role="metadata"),
            DatasetDimension(id="quaternary", label="Incidențe SKU în bonuri", kind="number", role="metadata"),
            DatasetDimension(id="progress_pct", label="Progres", kind="number", role="metadata"),
            DatasetDimension(id="risk", label="Risc", kind="string", role="metadata"),
        ],
        rows=_sorted_rows(breakdown_rows, query.sort, query.limit),
    )


def _error_result(
    query: WidgetQuery,
    code: QueryErrorCode,
    message: str,
    *,
    retryable: bool = False,
) -> WidgetQueryResult:
    return WidgetQueryResult(
        widget_id=query.widget_id,
        query=query,
        error=QueryError(code=code, message=message, retryable=retryable),
    )


async def execute_query_batch(
    repository: AnalyticsRepository,
    request: QueryBatchRequest,
    base_scope: AnalyticsScope,
    user: UserContext,
    *,
    deadline_ms: int,
) -> QueryBatchResponse:
    started = time.monotonic()
    snapshot = await repository.resolve_snapshot(base_scope)
    if request.snapshot_id and request.snapshot_id != snapshot.id:
        raise SnapshotConflictError(request.snapshot_id, snapshot.id)

    valid: dict[str, tuple[WidgetQuery, MetricDefinition, AnalyticsScope]] = {}
    results: dict[str, WidgetQueryResult] = {}
    for query in request.widgets:
        try:
            metric = _metric_for(query, user)
            if query.time_range is not None and query.time_range.end != base_scope.period:
                raise QueryValidationFailure("time_range.end trebuie să fie perioada snapshotului comun.")
            query_scope = resolve_query_scope(base_scope, query)
            unavailable_domains = [
                domain.value
                for domain in required_source_domains(query)
                if (source := snapshot.sources.get(domain.value)) is None or source.status is SourceStatus.UNAVAILABLE
            ]
            if unavailable_domains:
                results[query.widget_id] = _error_result(
                    query,
                    QueryErrorCode.UNAVAILABLE,
                    f"Sursele {', '.join(unavailable_domains)} nu sunt disponibile în snapshot.",
                )
                continue
            valid[query.widget_id] = (query, metric, query_scope)
        except PermissionError as exc:
            results[query.widget_id] = _error_result(query, QueryErrorCode.UNAUTHORIZED, str(exc))
        except QueryValidationFailure as exc:
            results[query.widget_id] = _error_result(query, QueryErrorCode.INVALID_QUERY, exc.message)

    fetches: dict[tuple[ModuleId, str], asyncio.Task[ModuleAnalyticsResponse]] = {}
    comparison_keys: dict[str, dict[QueryComparison, tuple[ModuleId, str]]] = {}
    for query, _metric, query_scope in valid.values():
        key = (query.module, query_scope.model_dump_json())
        if key not in fetches:
            fetches[key] = asyncio.create_task(repository.get_module(query.module, query_scope))
        comparison_keys[query.widget_id] = {}
        for comparison, comparison_scope in comparison_scopes(query_scope, query).items():
            comparison_key = (query.module, comparison_scope.model_dump_json())
            if comparison_key not in fetches:
                fetches[comparison_key] = asyncio.create_task(repository.get_module(query.module, comparison_scope))
            comparison_keys[query.widget_id][comparison] = comparison_key

    elapsed_ms = int((time.monotonic() - started) * 1000)
    remaining = max((deadline_ms - elapsed_ms) / 1000, 0)
    if fetches:
        done, pending = await asyncio.wait(fetches.values(), timeout=remaining)
    else:
        done, pending = set(), set()
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    task_by_key = {key: task for key, task in fetches.items()}
    for widget_id, (query, metric, query_scope) in valid.items():
        task = task_by_key[(query.module, query_scope.model_dump_json())]
        widget_comparison_tasks = {
            comparison: task_by_key[key] for comparison, key in comparison_keys[widget_id].items()
        }
        if task not in done or any(item not in done for item in widget_comparison_tasks.values()):
            results[widget_id] = _error_result(
                query,
                QueryErrorCode.DEADLINE_EXCEEDED,
                "Deadline-ul comun al dashboardului a fost depășit.",
                retryable=True,
            )
            continue
        try:
            response = task.result()
            comparison_responses = {
                comparison: comparison_task.result() for comparison, comparison_task in widget_comparison_tasks.items()
            }
            domain = primary_source_domain(query)
            source = snapshot.sources.get(domain.value)
            if source is None or source.status is SourceStatus.UNAVAILABLE:
                raise RuntimeError("Source eligibility changed inside one immutable snapshot.")
            dataset = _dataset(query, response, comparison_responses)
            sources = {
                source_domain.value: source_metadata
                for source_domain in required_source_domains(query)
                if (source_metadata := snapshot.sources.get(source_domain.value)) is not None
            }
            results[widget_id] = WidgetQueryResult(
                widget_id=widget_id,
                query=query,
                dataset=dataset,
                meta=QueryExecutionMeta(
                    period=query_scope.period,
                    scope_label=scope_label(query_scope),
                    snapshot_id=snapshot.id,
                    source=source,
                    sources=sources,
                    metric_id=metric.id,
                    metric_version=metric.version,
                    query_contract_version=query.query_contract_version,
                    warnings=source.warnings,
                ),
            )
        except Exception:
            results[widget_id] = _error_result(
                query,
                QueryErrorCode.INTERNAL,
                "Widgetul nu a putut fi executat.",
                retryable=True,
            )

    elapsed_ms = int((time.monotonic() - started) * 1000)
    remaining = max((deadline_ms - elapsed_ms) / 1000, 0)
    try:
        resolved_after = await asyncio.wait_for(repository.resolve_snapshot(base_scope), timeout=remaining)
    except TimeoutError:
        for widget_id, (query, _metric, _scope) in valid.items():
            results[widget_id] = _error_result(
                query,
                QueryErrorCode.DEADLINE_EXCEEDED,
                "Snapshotul nu a putut fi reconfirmat în deadline-ul comun.",
                retryable=True,
            )
    else:
        if resolved_after.id != snapshot.id:
            raise SnapshotConflictError(snapshot.id, resolved_after.id)

    return QueryBatchResponse(
        snapshot=snapshot,
        results=[results[query.widget_id] for query in request.widgets],
        deadline_ms=deadline_ms,
    )


def dataset_page(dataset: QueryDataset, page: int, page_size: int) -> QueryDataset:
    start = (page - 1) * page_size
    return dataset.model_copy(update={"rows": dataset.rows[start : start + page_size]})
