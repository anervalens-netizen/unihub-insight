from __future__ import annotations

from dataclasses import dataclass

from unihub_insight_api.domain import (
    AnalyticsScope,
    Capability,
    ChartKind,
    DashboardCreateRequest,
    DashboardDocument,
    DashboardVisibility,
    FilterMode,
    ModuleId,
    QueryBatchRequest,
    UserContext,
)
from unihub_insight_api.services.metric_catalog import (
    METRIC_CATALOG,
    PORTFOLIO_DIMENSIONS,
    PORTFOLIO_METRIC_IDS,
    metric_entity_dimension,
)

CATALOG_METRICS = {metric.id: metric for metric in METRIC_CATALOG}
COMMERCIAL_CAMPAIGN_METRICS = frozenset(
    metric_id
    for metric_id in CATALOG_METRICS
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

MODULE_CAPABILITIES: dict[ModuleId, Capability] = {
    ModuleId.SALES: Capability.ANALYTICS,
    ModuleId.PERFORMANCE: Capability.ANALYTICS,
    ModuleId.CAMPAIGNS: Capability.ANALYTICS,
    ModuleId.WORKFORCE: Capability.MANAGEMENT,
    ModuleId.COMPENSATION: Capability.HR,
    ModuleId.FINANCE: Capability.PNL,
    ModuleId.PLANNING: Capability.MANAGEMENT,
}

MODULE_METRICS: dict[ModuleId, frozenset[str]] = {
    ModuleId.SALES: frozenset(
        {
            "sales.total",
            "target.progress_pct",
            "receipts.average_value",
            "receipts.total",
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
        {
            "compensation.payroll",
            "compensation.average",
            "compensation.median",
            "compensation.sales_ratio",
        }
    ),
    ModuleId.FINANCE: frozenset({"finance.revenue", "finance.ebit", "finance.ebit_margin", "finance.operating_costs"}),
    ModuleId.PLANNING: frozenset({"planning.forecast", "planning.target_gap", "planning.accuracy", "planning.actual"}),
}

MODULE_CHARTS: dict[ModuleId, frozenset[ChartKind]] = {
    ModuleId.SALES: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.AREA,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.HEATMAP,
            ChartKind.CALENDAR,
            ChartKind.TABLE,
        }
    ),
    ModuleId.PERFORMANCE: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.HEATMAP,
            ChartKind.SCATTER,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        }
    ),
    ModuleId.CAMPAIGNS: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.AREA,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.HEATMAP,
            ChartKind.TABLE,
        }
    ),
    ModuleId.WORKFORCE: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.HEATMAP,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        }
    ),
    ModuleId.COMPENSATION: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.HEATMAP,
            ChartKind.SCATTER,
            ChartKind.HISTOGRAM,
            ChartKind.BOXPLOT,
            ChartKind.TABLE,
        }
    ),
    ModuleId.FINANCE: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.AREA,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.TREEMAP,
            ChartKind.HEATMAP,
            ChartKind.WATERFALL,
            ChartKind.TABLE,
        }
    ),
    ModuleId.PLANNING: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.AREA,
            ChartKind.BAR,
            ChartKind.HEATMAP,
            ChartKind.SCATTER,
            ChartKind.TABLE,
        }
    ),
}

ALLOWED_FILTER_KEYS = frozenset({"firm", "regional", "asm", "stores", "agent"})
ALLOWED_OPTION_KEYS = frozenset({"show_legend", "show_labels", "top_n", "renderer", "smooth", "stacked", "pixel_ratio"})
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


def widget_dimensions(widget: object) -> tuple[str, ...]:
    configured = tuple(getattr(widget, "dimensions", ()))
    legacy = getattr(widget, "dimension", None)
    return configured or (() if legacy is None else (legacy,))


@dataclass(frozen=True)
class DashboardValidationError(ValueError):
    errors: tuple[str, ...]

    def __str__(self) -> str:
        return "; ".join(self.errors)


@dataclass(frozen=True)
class DashboardCapabilityError(PermissionError):
    capability: Capability

    def __str__(self) -> str:
        return f"Capability {self.capability.value} is required."


def required_capabilities(
    request: DashboardCreateRequest | DashboardDocument,
) -> frozenset[Capability]:
    return frozenset(MODULE_CAPABILITIES[widget.module] for widget in request.widgets)


def user_can_read(document: DashboardDocument, user: UserContext) -> bool:
    if document.owner_subject != user.subject and Capability.ADMIN not in user.capabilities:
        permission = next((entry.permission for entry in document.acl if entry.subject == user.subject), None)
        if permission is None and document.visibility is not DashboardVisibility.SHARED:
            return False
    return required_capabilities(document).issubset(user.capabilities)


def user_can_write(document: DashboardDocument, user: UserContext) -> bool:
    if document.owner_subject == user.subject or Capability.ADMIN in user.capabilities:
        return True
    permission = next((entry.permission for entry in document.acl if entry.subject == user.subject), None)
    return permission is not None and permission.value in {"edit", "admin"}


def user_can_admin(document: DashboardDocument, user: UserContext) -> bool:
    if document.owner_subject == user.subject or Capability.ADMIN in user.capabilities:
        return True
    permission = next((entry.permission for entry in document.acl if entry.subject == user.subject), None)
    return permission is not None and permission.value == "admin"


def dashboard_allows_scope(document: DashboardDocument, scope: AnalyticsScope) -> bool:
    ceiling = document.scope_ceiling
    if ceiling.firms and scope.firm not in ceiling.firms:
        return False
    if ceiling.regionals and (not scope.regional or not set(scope.regional).issubset(ceiling.regionals)):
        return False
    if ceiling.asms and scope.asm not in ceiling.asms:
        return False
    if ceiling.stores and (not scope.stores or not set(scope.stores).issubset(ceiling.stores)):
        return False
    return ceiling.allow_agent or not scope.agent


def validate_batch_for_dashboard(document: DashboardDocument, request: QueryBatchRequest) -> None:
    stored = {widget.id: widget for widget in document.widgets}
    if request.dashboard_id != document.id:
        raise ValueError("Dashboard ID mismatch.")
    for query in request.widgets:
        widget = stored.get(query.widget_id)
        if widget is None:
            raise ValueError(f"Widget {query.widget_id} is not part of the dashboard.")
        if (
            query.module is not widget.module
            or query.metric_id != widget.metric_id
            or query.metric_version != widget.metric_version
            or query.query_contract_version != widget.query_contract_version
            or query.visualization is not widget.visualization
            or query.time_grain != widget.time_grain
            or query.dimensions != widget_dimensions(widget)
            or query.limit != widget.limit
        ):
            raise ValueError(f"Widget {query.widget_id} query differs from its saved contract.")


def validate_dashboard(request: DashboardCreateRequest, user: UserContext) -> None:
    missing = required_capabilities(request) - user.capabilities
    if missing:
        raise DashboardCapabilityError(sorted(missing, key=lambda item: item.value)[0])

    errors: list[str] = []
    if request.query_contract_version != 1:
        errors.append("query_contract_version is not supported")
    acl_subjects = [entry.subject for entry in request.acl]
    if len(set(acl_subjects)) != len(acl_subjects):
        errors.append("acl contains duplicate subjects")
    seen_ids: set[str] = set()
    for index, widget in enumerate(request.widgets):
        prefix = f"widgets[{index}]"
        if widget.id in seen_ids:
            errors.append(f"{prefix}.id is duplicated")
        seen_ids.add(widget.id)
        if widget.metric_id not in MODULE_METRICS[widget.module]:
            errors.append(f"{prefix}.metric_id is not registered for {widget.module.value}")
        metric = CATALOG_METRICS.get(widget.metric_id)
        dimensions = widget_dimensions(widget)
        if len(set(dimensions)) != len(dimensions):
            errors.append(f"{prefix}.dimensions contains duplicates")
        if widget.dimensions and widget.dimension not in {None, widget.dimensions[0]}:
            errors.append(f"{prefix}.dimension legacy alias differs from dimensions[0]")
        if metric is None:
            errors.append(f"{prefix}.metric_id is missing from the metric catalog")
        elif widget.visualization not in metric.allowed_shapes:
            errors.append(f"{prefix}.visualization is incompatible with {widget.metric_id}")
        elif any(dimension not in metric.allowed_dimensions for dimension in dimensions):
            errors.append(f"{prefix}.dimensions are incompatible with {widget.metric_id}")
        elif widget.time_grain not in metric.allowed_grains:
            errors.append(f"{prefix}.time_grain is incompatible with {widget.metric_id}")
        if widget.metric_id in SCALAR_ONLY_METRICS and dimensions:
            errors.append(f"{prefix}.metric_id supports only an aggregate without dimension")
        if widget.metric_id in PORTFOLIO_METRIC_IDS and (
            len(dimensions) != 1 or dimensions[0] not in PORTFOLIO_DIMENSIONS
        ):
            errors.append(f"{prefix}.portfolio requires exactly one taxonomy dimension")
        if widget.visualization in {ChartKind.LINE, ChartKind.AREA} and dimensions != ("time",):
            errors.append(f"{prefix}.visualization requires dimensions=[time]")
        mix_dimensions = {
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
        if widget.visualization in {ChartKind.DONUT, ChartKind.TREEMAP}:
            if widget.metric_id in PORTFOLIO_METRIC_IDS:
                if metric is None or len(dimensions) != 1 or dimensions[0] not in metric.allowed_dimensions:
                    errors.append(f"{prefix}.visualization requires the portfolio metric dimension")
            elif dimensions != (mix_dimensions.get(widget.metric_id),):
                errors.append(f"{prefix}.visualization requires the approved aggregate dimension")
        if widget.visualization is ChartKind.WATERFALL and (
            widget.metric_id != "finance.ebit" or dimensions != ("category",)
        ):
            errors.append(f"{prefix}.waterfall requires finance.ebit × category")
        if widget.visualization is ChartKind.CALENDAR and (
            widget.module is not ModuleId.SALES
            or widget.metric_id != "sales.total"
            or dimensions != ("time",)
            or widget.time_grain != "day"
        ):
            errors.append(f"{prefix}.calendar requires sales.total × time at day grain")
        if len(dimensions) > 1 and widget.visualization is not ChartKind.HEATMAP:
            errors.append(f"{prefix}.two dimensions require heatmap")
        if widget.visualization is ChartKind.HEATMAP and dimensions != (
            metric_entity_dimension(widget.module, widget.metric_id),
            "time",
        ):
            errors.append(f"{prefix}.heatmap requires the module entity dimension and time")
        if widget.visualization in {ChartKind.HISTOGRAM, ChartKind.BOXPLOT, ChartKind.SCATTER} and (
            not dimensions or "time" in dimensions
        ):
            errors.append(f"{prefix}.visualization requires an entity dimension")
        if widget.visualization not in MODULE_CHARTS[widget.module]:
            errors.append(f"{prefix}.visualization is incompatible with {widget.module.value}")
        if widget.layout.x + widget.layout.w > 24:
            errors.append(f"{prefix}.layout exceeds the 24-column canvas")
        unknown_filters = set(widget.filters) - ALLOWED_FILTER_KEYS
        if unknown_filters:
            errors.append(f"{prefix}.filters contains unsupported keys: {', '.join(sorted(unknown_filters))}")
        unknown_options = set(widget.options) - ALLOWED_OPTION_KEYS
        if unknown_options:
            errors.append(f"{prefix}.options contains unsupported keys: {', '.join(sorted(unknown_options))}")
        boolean_options = {"show_legend", "show_labels", "smooth", "stacked"}
        invalid_boolean_options = sorted(
            key for key in boolean_options if key in widget.options and not isinstance(widget.options[key], bool)
        )
        if invalid_boolean_options:
            errors.append(f"{prefix}.options requires booleans for: {', '.join(invalid_boolean_options)}")
        top_n = widget.options.get("top_n")
        if top_n is not None and (
            isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= widget.limit
        ):
            errors.append(f"{prefix}.options.top_n must be an integer between 1 and limit")
        if widget.options.get("renderer", "canvas") != "canvas":
            errors.append(f"{prefix}.options.renderer supports only canvas")
        pixel_ratio = widget.options.get("pixel_ratio", 2)
        if isinstance(pixel_ratio, bool) or pixel_ratio not in {1, 2}:
            errors.append(f"{prefix}.options.pixel_ratio must be 1 or 2")
        if widget.metric_version != 1 or widget.query_contract_version != 1:
            errors.append(f"{prefix} references an unsupported contract version")
        if widget.filter_mode is FilterMode.IGNORE and widget.filters:
            errors.append(f"{prefix}.filters must be empty when filter_mode=ignore")
        if widget.module in {ModuleId.FINANCE, ModuleId.PLANNING} and "agent" in widget.filters:
            errors.append(f"{prefix}.filters.agent is incompatible with {widget.module.value}")
        if widget.metric_id in VISIT_METRICS and "agent" in widget.filters:
            errors.append(f"{prefix}.filters.agent is incompatible with Team Leader visits")
    if errors:
        raise DashboardValidationError(tuple(errors))
