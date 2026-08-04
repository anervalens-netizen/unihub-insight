from decimal import Decimal

from unihub_insight_api.domain import AnalyticsScope
from unihub_insight_api.repositories.postgres_modules import (
    append_reporting_scope,
    finance_metrics,
    shift_month,
)


def test_shift_month_crosses_year_boundaries() -> None:
    assert shift_month("2026-01", -1) == "2025-12"
    assert shift_month("2026-12", 1) == "2027-01"


def test_store_scope_dominates_parent_filters_in_sql() -> None:
    params: list[object] = ["2026-08"]
    clauses = append_reporting_scope(
        AnalyticsScope(
            period="2026-08",
            firm="MOBIUP",
            regional="Sud",
            stores=("S001", "S002"),
        ),
        alias="agg",
        params=params,
    )
    sql = " AND ".join(clauses)
    assert "agg.site_code = ANY($2::text[])" in sql
    assert "agg.firma" not in sql
    assert "agg.regional" not in sql
    assert params == ["2026-08", ["S001", "S002"]]


def test_finance_metrics_follow_retail_category_contract() -> None:
    result = finance_metrics(
        {
            "v1": Decimal("1000"),
            "c1": Decimal("300"),
            "c3": Decimal("200"),
            "a1": Decimal("50"),
        }
    )
    assert result["revenue"] == Decimal("1000.00")
    assert result["gross_margin"] == Decimal("700.00")
    assert result["ebitda"] == Decimal("500.00")
    assert result["ebit"] == Decimal("450.00")
