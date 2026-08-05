from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from unihub_insight_api.domain import (
    AlertSeverity,
    AnalyticsScope,
    BreakdownRow,
    InsightAlert,
    KpiMetric,
    ModuleAnalyticsResponse,
    RiskLevel,
)
from unihub_insight_api.repositories.postgres import _money, _percent, _ratio
from unihub_insight_api.repositories.postgres_modules import (
    PostgresInsightRepository,
    append_reporting_scope,
    finance_metrics,
)

MIN_SALARY_FOR_AVERAGE = Decimal("2000")
MIN_COMPENSATION_POPULATION = 3


@dataclass(frozen=True)
class SalaryStatistics:
    total: Decimal
    average: Decimal
    median: Decimal
    eligible_average_count: int


def salary_statistics(values: Sequence[Decimal]) -> SalaryStatistics:
    salaries = sorted(_money(value) for value in values)
    total = sum(salaries, Decimal(0))
    eligible = [value for value in salaries if value >= MIN_SALARY_FOR_AVERAGE]
    average = _money(sum(eligible, Decimal(0)) / Decimal(len(eligible))) if eligible else Decimal(0)
    if not salaries:
        median = Decimal(0)
    else:
        middle = len(salaries) // 2
        median = (
            salaries[middle] if len(salaries) % 2 else _money((salaries[middle - 1] + salaries[middle]) / Decimal(2))
        )
    return SalaryStatistics(
        total=_money(total),
        average=average,
        median=median,
        eligible_average_count=len(eligible),
    )


def compensation_is_suppressed(person_count: int) -> bool:
    return 0 < person_count < MIN_COMPENSATION_POPULATION


class PostgresHardenedInsightRepository(PostgresInsightRepository):
    """Final read adapter with privacy and period-consistency corrections."""

    async def _workforce_coverage(self, scope: AnalyticsScope) -> tuple[int, int]:
        eligible_params: list[Any] = []
        eligible_clauses = append_reporting_scope(
            scope,
            alias="store",
            params=eligible_params,
            include_agent=False,
        )
        if not scope.stores:
            eligible_clauses.append("store.is_active = TRUE")

        staffed_params: list[Any] = [scope.period]
        staffed_clauses = ["agg.import_month = $1"]
        staffed_clauses.extend(
            append_reporting_scope(
                scope,
                alias="agg",
                params=staffed_params,
                include_agent=True,
            )
        )

        async with self.pool.acquire() as connection:
            eligible = await connection.fetchval(
                f"""
                SELECT COUNT(DISTINCT store.site_code)::INT
                FROM stores store
                WHERE {" AND ".join(eligible_clauses)}
                """,
                *eligible_params,
            )
            staffed = await connection.fetchval(
                f"""
                SELECT COUNT(DISTINCT agg.site_code)::INT
                FROM reporting_agent_month agg
                WHERE {" AND ".join(staffed_clauses)}
                  AND agg.working_days > 0
                """,
                *staffed_params,
            )
        return int(eligible or 0), int(staffed or 0)

    async def _workforce(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        response = await super()._workforce(scope)
        eligible, staffed = await self._workforce_coverage(scope)
        coverage = _percent(Decimal(staffed) * Decimal("100") / Decimal(eligible)) if eligible > 0 else None
        kpis: list[KpiMetric] = []
        for kpi in response.kpis:
            if kpi.id == "workforce.coverage":
                kpis.append(
                    kpi.model_copy(
                        update={
                            "value": coverage or Decimal(0),
                            "supporting_value": Decimal(staffed),
                            "supporting_label": f"{staffed} din {eligible} magazine eligibile",
                            "risk": (
                                RiskLevel.HEALTHY
                                if coverage is not None and coverage >= Decimal("95")
                                else RiskLevel.WATCH
                            ),
                        }
                    )
                )
            else:
                kpis.append(kpi)
        alerts = list(response.alerts)
        if eligible > staffed:
            alerts.append(
                InsightAlert(
                    id="workforce-uncovered-stores",
                    severity=AlertSeverity.WARNING,
                    title="Magazine fără acoperire",
                    description=(
                        f"{eligible - staffed} din {eligible} magazine eligibile nu au personal "
                        "cu zile lucrate în perioada selectată."
                    ),
                )
            )
        return response.model_copy(update={"kpis": kpis, "alerts": alerts[:8]})

    async def _compensation(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        response = await super()._compensation(scope)
        rows = await self._salary_rows(scope)
        year, month = (int(part) for part in scope.period.split("-"))
        current = [row for row in rows if int(row["year"]) == year and int(row["month"]) == month]
        values = [_money(row["total_salary"]) for row in current]
        stats = salary_statistics(values)

        if compensation_is_suppressed(len(values)):
            return response.model_copy(
                update={
                    "kpis": [],
                    "trend": [],
                    "distribution": [],
                    "breakdown": [],
                    "matrix": [],
                    "alerts": [
                        InsightAlert(
                            id="compensation-population-suppressed",
                            severity=AlertSeverity.CRITICAL,
                            title="Rezultat salarial suprimat",
                            description=(
                                "Scope-ul curent conține mai puțin de trei persoane. "
                                "Valorile și exporturile sunt ascunse pentru a evita "
                                "dezvăluirea indirectă a remunerației individuale."
                            ),
                        )
                    ],
                }
            )

        kpis: list[KpiMetric] = []
        for kpi in response.kpis:
            if kpi.id == "compensation.payroll":
                kpis.append(kpi.model_copy(update={"value": stats.total}))
            elif kpi.id == "compensation.average":
                kpis.append(
                    kpi.model_copy(
                        update={
                            "value": stats.average,
                            "supporting_value": Decimal(stats.eligible_average_count),
                            "supporting_label": "Persoane cu minimum 2.000 RON",
                        }
                    )
                )
            elif kpi.id == "compensation.median":
                kpis.append(kpi.model_copy(update={"value": stats.median}))
            else:
                kpis.append(kpi)
        return response.model_copy(update={"kpis": kpis})

    async def _finance(self, scope: AnalyticsScope) -> ModuleAnalyticsResponse:
        response = await super()._finance(scope)
        rows = await self._finance_rows(scope)
        current_rows = [
            row
            for row in rows
            if row["period"].strftime("%Y-%m") == scope.period
            and str(row["source_site_code"]) != "__FINANCE_UNALLOCATED__"
        ]
        amounts_by_store: dict[tuple[str, str], dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        labels: dict[tuple[str, str], tuple[str, str]] = {}
        for row in current_rows:
            key = (str(row["company_name"]), str(row["canonical_site_code"]))
            amounts_by_store[key][str(row["category_code"])] += _money(row["amount"])
            labels[key] = (str(row["source_location_name"]), str(row["regional"]))

        breakdown: list[BreakdownRow] = []
        for key, amounts in amounts_by_store.items():
            metrics = finance_metrics(amounts)
            label, regional = labels[key]
            margin = _ratio(metrics["ebit"], metrics["revenue"])
            breakdown.append(
                BreakdownRow(
                    id=f"{key[0]}:{key[1]}",
                    label=label,
                    context=f"{key[0]} · {regional} · {scope.period}",
                    primary=metrics["revenue"],
                    secondary=metrics["ebit"],
                    tertiary=metrics["operating_costs"],
                    progress_pct=margin,
                    risk=(RiskLevel.RISK if metrics["ebit"] < 0 else RiskLevel.HEALTHY),
                )
            )
        breakdown.sort(key=lambda item: item.secondary or Decimal(0))

        alerts = [alert for alert in response.alerts if alert.id != "finance-negative"]
        negative_count = sum(1 for item in breakdown if item.secondary is not None and item.secondary < 0)
        if negative_count:
            alerts.insert(
                0,
                InsightAlert(
                    id="finance-negative",
                    severity=AlertSeverity.CRITICAL,
                    title="Magazine cu EBIT negativ",
                    description=(f"{negative_count} magazine au EBIT negativ în luna {scope.period}."),
                ),
            )
        return response.model_copy(update={"breakdown": breakdown, "alerts": alerts[:8]})
