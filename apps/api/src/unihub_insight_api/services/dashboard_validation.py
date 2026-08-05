from __future__ import annotations

from dataclasses import dataclass

from unihub_insight_api.domain import (
    Capability,
    ChartKind,
    DashboardCreateRequest,
    DashboardDocument,
    FilterMode,
    ModuleId,
    UserContext,
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
        }
    ),
    ModuleId.PERFORMANCE: frozenset(
        {
            "performance.average",
            "performance.at_target",
            "performance.volatility",
            "performance.daily_productivity",
        }
    ),
    ModuleId.CAMPAIGNS: frozenset(
        {
            "campaigns.focus_sales",
            "campaigns.focus_share",
            "campaigns.active_stores",
            "campaigns.active_products",
        }
    ),
    ModuleId.WORKFORCE: frozenset(
        {
            "workforce.headcount",
            "workforce.productivity",
            "workforce.coverage",
            "workforce.stability",
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
    ModuleId.FINANCE: frozenset(
        {"finance.revenue", "finance.ebit", "finance.ebit_margin", "finance.operating_costs"}
    ),
    ModuleId.PLANNING: frozenset(
        {"planning.forecast", "planning.target_gap", "planning.accuracy", "planning.actual"}
    ),
}

MODULE_CHARTS: dict[ModuleId, frozenset[ChartKind]] = {
    ModuleId.SALES: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.AREA,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.HEATMAP,
            ChartKind.SCATTER,
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
            ChartKind.HEATMAP,
            ChartKind.TABLE,
        }
    ),
    ModuleId.COMPENSATION: frozenset(
        {
            ChartKind.KPI,
            ChartKind.LINE,
            ChartKind.BAR,
            ChartKind.DONUT,
            ChartKind.HEATMAP,
            ChartKind.SCATTER,
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
    if document.owner_subject != user.subject and document.visibility.value != "shared":
        return False
    return required_capabilities(document).issubset(user.capabilities)


def validate_dashboard(request: DashboardCreateRequest, user: UserContext) -> None:
    missing = required_capabilities(request) - user.capabilities
    if missing:
        raise DashboardCapabilityError(sorted(missing, key=lambda item: item.value)[0])

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, widget in enumerate(request.widgets):
        prefix = f"widgets[{index}]"
        if widget.id in seen_ids:
            errors.append(f"{prefix}.id is duplicated")
        seen_ids.add(widget.id)
        if widget.metric_id not in MODULE_METRICS[widget.module]:
            errors.append(f"{prefix}.metric_id is not registered for {widget.module.value}")
        if widget.visualization not in MODULE_CHARTS[widget.module]:
            errors.append(f"{prefix}.visualization is incompatible with {widget.module.value}")
        if widget.layout.x + widget.layout.w > 24:
            errors.append(f"{prefix}.layout exceeds the 24-column canvas")
        unknown_filters = set(widget.filters) - ALLOWED_FILTER_KEYS
        if unknown_filters:
            errors.append(
                f"{prefix}.filters contains unsupported keys: {', '.join(sorted(unknown_filters))}"
            )
        if widget.filter_mode is FilterMode.IGNORE and widget.filters:
            errors.append(f"{prefix}.filters must be empty when filter_mode=ignore")
        if widget.module in {ModuleId.FINANCE, ModuleId.PLANNING} and "agent" in widget.filters:
            errors.append(f"{prefix}.filters.agent is incompatible with {widget.module.value}")
    if errors:
        raise DashboardValidationError(tuple(errors))
