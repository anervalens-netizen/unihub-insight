from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from unihub_insight_api.domain import (
    AlertSeverity,
    AnalyticsScope,
    InsightAlert,
    KpiMetric,
    ModuleAnalyticsResponse,
    RiskLevel,
)
from unihub_insight_api.repositories.postgres import _money, _percent
from unihub_insight_api.repositories.postgres_modules import (
    PostgresInsightRepository,
    append_reporting_scope,
)


@dataclass(frozen=True)
class SalaryStatistics:
    total: Decimal
    average: Decimal
    median: Decimal
    eligible_average_count: int


def salary_statistics(values: Sequence[Decimal]) -> SalaryStatistics:
    salaries = sorted(_money(value) for value in values)
    total = sum(salaries, Decimal(0))
    average = _money(total / Decimal(len(salaries))) if salaries else Decimal(0)
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
        eligible_average_count=len(salaries),
    )


class PostgresHardenedInsightRepository(PostgresInsightRepository):
    """Final read adapter with period-consistency corrections."""

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
