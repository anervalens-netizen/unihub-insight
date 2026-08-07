from __future__ import annotations

from datetime import UTC, datetime

from unihub_insight_api.domain import (
    AlertSeverity,
    AnalyticalSnapshot,
    AnalyticsScope,
    Capability,
    DataMode,
    InsightAlert,
    ModuleAnalyticsResponse,
    ModuleId,
    OverviewMeta,
    SourceDomain,
    SourceStatus,
)
from unihub_insight_api.services.scope import scope_label

MODULE_SOURCE_DOMAINS: dict[ModuleId, tuple[SourceDomain, ...]] = {
    ModuleId.SALES: (SourceDomain.SALES,),
    ModuleId.PERFORMANCE: (SourceDomain.SALES,),
    ModuleId.CAMPAIGNS: (SourceDomain.CAMPAIGNS, SourceDomain.CONTEST),
    ModuleId.WORKFORCE: (SourceDomain.WORKFORCE, SourceDomain.VISITS, SourceDomain.GRILE),
    ModuleId.COMPENSATION: (SourceDomain.COMPENSATION,),
    ModuleId.FINANCE: (SourceDomain.FINANCE,),
    ModuleId.PLANNING: (SourceDomain.PLANNING, SourceDomain.SALES),
}

# These modules compose independent, governed sub-views.  The route must let
# the repository expose each slice's own availability when at least one source
# is eligible.  Sensitive modules deliberately remain outside this set: their
# complete source contracts fail closed before any read is attempted.
MIXED_SLICE_MODULES = frozenset({ModuleId.CAMPAIGNS, ModuleId.WORKFORCE})

MODULE_PRESENTATION: dict[ModuleId, tuple[str, str, Capability]] = {
    ModuleId.SALES: ("Sales Intelligence", "Pace, trend, mix și calitatea tranzacțiilor.", Capability.ANALYTICS),
    ModuleId.PERFORMANCE: (
        "Performance",
        "Target, stabilitate și prioritizare pe structură comercială.",
        Capability.ANALYTICS,
    ),
    ModuleId.CAMPAIGNS: (
        "Campaigns",
        "Focus și mecanisme comerciale peste aceeași sursă de adevăr.",
        Capability.ANALYTICS,
    ),
    ModuleId.WORKFORCE: (
        "Workforce",
        "Activitate comercială observată, productivitate și Grile; nu reprezintă registru oficial de personal.",
        Capability.MANAGEMENT,
    ),
    ModuleId.COMPENSATION: (
        "Compensation",
        "Cost salarial, distribuție și relația cu performanța.",
        Capability.HR,
    ),
    ModuleId.FINANCE: (
        "Finance & P&L",
        "Venit, cost, profit, marjă și reconciliere actual/estimat.",
        Capability.PNL,
    ),
    ModuleId.PLANNING: (
        "Planning",
        "Forecast, target, acuratețe și scenarii comerciale.",
        Capability.MANAGEMENT,
    ),
}


def unavailable_source_domains(module: ModuleId, snapshot: AnalyticalSnapshot) -> tuple[SourceDomain, ...]:
    unavailable = tuple(
        domain
        for domain in MODULE_SOURCE_DOMAINS[module]
        if (source := snapshot.sources.get(domain.value)) is None or source.status is SourceStatus.UNAVAILABLE
    )
    if module in MIXED_SLICE_MODULES and len(unavailable) != len(MODULE_SOURCE_DOMAINS[module]):
        return ()
    return unavailable


def unavailable_module_response(
    module: ModuleId,
    scope: AnalyticsScope,
    snapshot: AnalyticalSnapshot,
    domains: tuple[SourceDomain, ...],
) -> ModuleAnalyticsResponse:
    title, description, capability = MODULE_PRESENTATION[module]
    required_sources = {
        domain: source
        for domain in MODULE_SOURCE_DOMAINS[module]
        if (source := snapshot.sources.get(domain.value)) is not None
    }
    primary = required_sources.get(MODULE_SOURCE_DOMAINS[module][0])
    names = ", ".join(domain.value for domain in domains)
    warning = f"Sursele {names} nu sunt disponibile în snapshotul eligibil."
    return ModuleAnalyticsResponse(
        meta=OverviewMeta(
            period=scope.period,
            comparison=scope.comparison,
            as_of=primary.as_of if primary else None,
            is_final=primary.is_final if primary else False,
            data_mode=DataMode.POSTGRES,
            scope_label=scope_label(scope),
            generated_at=datetime.now(UTC),
            source=primary.source if primary else "source-unavailable",
            analytical_snapshot_id=snapshot.id,
            snapshot_contract_version=snapshot.contract_version,
            sources=required_sources,
            warnings=(warning,),
        ),
        module=module,
        title=title,
        description=description,
        required_capability=capability,
        axes=(),
        supported_charts=(),
        kpis=[],
        trend=[],
        distribution=[],
        breakdown=[],
        matrix=[],
        alerts=[
            InsightAlert(
                id=f"{module.value}-source-unavailable",
                severity=AlertSeverity.WARNING,
                title="Sursă oficială indisponibilă",
                description=warning,
            )
        ],
    )
