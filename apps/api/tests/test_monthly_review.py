from decimal import Decimal

from fastapi.testclient import TestClient

from unihub_insight_api.domain import ReviewStatus
from unihub_insight_api.repositories.monthly_review import (
    Aggregate,
    bridge,
    classify_status,
)


def test_monthly_review_demo_contract(client: TestClient) -> None:
    response = client.get(
        "/api/v1/monthly-review",
        params={"period": "2026-07", "recent_months": 6},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recent_months"] == 6
    assert len(payload["executive"]) >= 8
    assert len(payload["trend"]) >= 7
    assert len(payload["seasonality"]) == 3
    assert payload["managers"]
    assert payload["stores"]
    assert payload["products"]
    assert payload["agents"]
    assert payload["methodology"]


def test_driver_bridge_reconciles_exact_difference() -> None:
    current = Aggregate(
        sales=Decimal("1500"),
        units=Decimal("15"),
        receipts=Decimal("10"),
    )
    baseline = Aggregate(
        sales=Decimal("1000"),
        units=Decimal("10"),
        receipts=Decimal("8"),
    )

    result = bridge(current, baseline, "test")

    assert (
        result.receipts_effect + result.units_per_receipt_effect + result.value_per_unit_effect
        == result.sales_difference
    )


def test_status_detects_recovery_and_simultaneous_risk() -> None:
    assert (
        classify_status(
            current=Decimal("90"),
            previous_year=Decimal("100"),
            recent_average=Decimal("80"),
            target_pct=Decimal("92"),
            yoy_pct=Decimal("-10"),
            recent_pct=Decimal("12.5"),
            consistency=Decimal("90"),
        )
        is ReviewStatus.RECOVERING
    )
    assert (
        classify_status(
            current=Decimal("70"),
            previous_year=Decimal("100"),
            recent_average=Decimal("95"),
            target_pct=Decimal("75"),
            yoy_pct=Decimal("-30"),
            recent_pct=Decimal("-26"),
            consistency=Decimal("80"),
        )
        is ReviewStatus.RISK
    )
