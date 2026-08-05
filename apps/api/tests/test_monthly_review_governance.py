from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from unihub_insight_api.domain import AnalyticsScope, ReviewStatus
from unihub_insight_api.main import create_app
from unihub_insight_api.repositories.monthly_review import (
    Aggregate,
    classify_status,
    executive_metrics,
    score_entity,
)
from unihub_insight_api.repositories.monthly_review_reporting import (
    MAX_REVIEW_PERIODS,
    ReportingMonthlyReviewRepository,
    validate_review_periods,
)
from unihub_insight_api.services.monthly_review_contract import (
    MONTHLY_REVIEW_DRIVER_FORMULA,
    MONTHLY_REVIEW_METRIC_IDS,
    MONTHLY_REVIEW_SCORING,
)


def test_every_executive_metric_is_governed() -> None:
    metrics = executive_metrics(Aggregate(), Aggregate(), Aggregate(), Aggregate())
    assert {metric.id for metric in metrics} == MONTHLY_REVIEW_METRIC_IDS


def test_scoring_contract_matches_runtime_formula() -> None:
    contract = MONTHLY_REVIEW_SCORING
    assert contract.total_weight == Decimal("1.00")

    target_pct = Decimal("108")
    yoy_pct = Decimal("12")
    recent_pct = Decimal("7")
    consistency = Decimal("82")

    target_component = min(max(target_pct / Decimal("1.2"), 0), 100)
    yoy_component = min(max(Decimal("50") + yoy_pct * Decimal("1.8"), 0), 100)
    recent_component = min(max(Decimal("50") + recent_pct * Decimal("2.2"), 0), 100)
    expected = (
        target_component * contract.target_weight
        + yoy_component * contract.yoy_weight
        + recent_component * contract.recent_weight
        + consistency * contract.consistency_weight
    ).quantize(Decimal("0.01"))

    assert (
        score_entity(
            target_pct=target_pct,
            yoy_pct=yoy_pct,
            recent_pct=recent_pct,
            consistency=consistency,
        )
        == expected
    )
    assert "receipts_effect" in MONTHLY_REVIEW_DRIVER_FORMULA


def test_status_thresholds_match_governed_contract() -> None:
    contract = MONTHLY_REVIEW_SCORING
    status = classify_status(
        current=Decimal("80"),
        previous_year=Decimal("100"),
        recent_average=Decimal("100"),
        target_pct=contract.risk_target_threshold - Decimal("0.01"),
        yoy_pct=-contract.meaningful_yoy_delta,
        recent_pct=-contract.meaningful_recent_delta,
        consistency=Decimal("90"),
    )
    assert status is ReviewStatus.RISK


def test_review_periods_are_strictly_bounded() -> None:
    assert validate_review_periods(["2026-07", "2026-07", "2026-06"]) == (
        "2026-07",
        "2026-06",
    )
    with pytest.raises(ValueError, match="bounded"):
        validate_review_periods(
            [f"2025-{month:02d}" for month in range(1, 13)]
            + ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"]
        )
    with pytest.raises(ValueError, match="YYYY-MM"):
        validate_review_periods(["2026-13"])
    assert MAX_REVIEW_PERIODS == 16


def test_active_repository_uses_reporting_models_not_raw_transactions() -> None:
    methods = (
        ReportingMonthlyReviewRepository._review_store_rows,
        ReportingMonthlyReviewRepository._review_agent_rows,
        ReportingMonthlyReviewRepository._review_product_rows,
    )
    source = "\n".join(inspect.getsource(method) for method in methods)
    assert "FROM reporting_agent_month" in source
    assert "FROM reporting_item_month" in source
    assert "insight.monthly_review_item_month" in source
    assert "sales_transactions" not in source

    app_source = inspect.getsource(create_app)
    assert "ReportingMonthlyReviewRepository" in app_source
    assert "PostgresMonthlyReviewRepository(" not in app_source


def test_monthly_targets_are_aggregated_before_joining() -> None:
    store_source = inspect.getsource(ReportingMonthlyReviewRepository._review_store_rows)
    agent_source = inspect.getsource(ReportingMonthlyReviewRepository._review_agent_rows)
    combined = f"{store_source}\n{agent_source}"

    assert combined.count("SUM(target.target_value) AS target_value") >= 3
    assert "GROUP BY target.import_month, target.site_code" in store_source
    assert "target.import_month" in agent_source
    assert "target.site_code" in agent_source
    assert "target.agent" in agent_source
    assert "LEFT JOIN targets USING (import_month, site_code)" in store_source
    assert "LEFT JOIN targets USING (import_month, site_code, agent)" in agent_source
    assert "LEFT JOIN agent_targets target USING" not in combined
    assert "LEFT JOIN store_targets store_target" not in combined


def test_governed_supplement_view_is_security_bounded() -> None:
    migration = Path("apps/api/migrations/002_monthly_review_item_month.sql").read_text(encoding="utf-8")
    assert "security_barrier = true" in migration
    assert "WHERE NOT sale.is_cartela" in migration
    assert "GRANT SELECT ON insight.monthly_review_item_month" in migration
    assert "GRANT SELECT ON TABLE sales_transactions TO unihub_insight_reader" not in migration


def test_reporting_scope_contract_remains_store_dominant() -> None:
    scope = AnalyticsScope(
        period="2026-07",
        firm="MOBIUP",
        regional="Sud",
        stores=("S001", "S002"),
    )
    params: list[object] = [["2026-07"]]
    clauses = ReportingMonthlyReviewRepository._scope_clauses(scope, params)
    sql = " AND ".join(clauses)
    assert "site_code = ANY" in sql
    assert ".firma" not in sql
    assert ".regional" not in sql
