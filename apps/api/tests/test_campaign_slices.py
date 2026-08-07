from decimal import Decimal
from inspect import getsource

from unihub_insight_api.domain.models import SourceDomain, SourceMetadata, SourceStatus
from unihub_insight_api.repositories.postgres_modules import PostgresInsightRepository


def campaign_row(
    mechanism: str,
    site_code: str,
    firm: str,
    *,
    sales: str,
    quantity: int,
    reward: str,
    qualifying: int | None = None,
    eligible: int | None = None,
    active_products: int | None = None,
    product_start: int = 0,
    mechanism_variant: str | None = None,
) -> dict[str, object]:
    is_promo = mechanism == "promo"
    return {
        "period": "2026-06",
        "mechanism": mechanism,
        "mechanism_variant": mechanism_variant,
        "campaign_key": f"{mechanism}-2026-06",
        "site_code": site_code,
        "locatie": f"Magazin {site_code}",
        "firma": firm,
        "regional": "RM Test",
        "actual_sales": Decimal(sales),
        "actual_quantity": quantity,
        "active_product_count": active_products or (3 if is_promo else 967),
        "active_product_codes": [
            f"P{index:04d}"
            for index in range(
                product_start,
                product_start + (active_products or (3 if is_promo else 967)),
            )
        ],
        "promo_qualifying_bons": (qualifying if qualifying is not None else 2) if is_promo else None,
        "promo_discounted_units": (eligible if eligible is not None else quantity) if is_promo else None,
        "promo_discount_value": Decimal(reward) if is_promo else None,
        "incentive_eligible_quantity": (eligible if eligible is not None else quantity - 1) if not is_promo else None,
        "incentive_qualified_quantity": (qualifying if qualifying is not None else quantity - 2)
        if not is_promo
        else None,
        "incentive_value": Decimal(reward) if not is_promo else None,
        "incentive_store_qualified": not is_promo,
        "status": "partial",
        "warnings": ["sales_snapshot_legacy_partial"],
    }


def kpi_values(slice_: object) -> dict[str, Decimal]:
    return {item.id: item.value for item in slice_.kpis}  # type: ignore[attr-defined]


def test_focus_active_products_uses_scope_union_not_largest_store() -> None:
    query_source = getsource(PostgresInsightRepository._campaign_rows)
    response_source = getsource(PostgresInsightRepository._campaigns)

    assert "COUNT(DISTINCT source.item_code)::INT AS scope_active_products" in query_source
    assert 'row["scope_active_products"]' in response_source
    assert "campaign_source.status is SourceStatus.UNAVAILABLE" in response_source
    assert "sales_source.status is SourceStatus.UNAVAILABLE" in response_source
    assert "status=focus_status" in response_source


def test_workforce_coverage_preserves_every_observed_store_per_agent() -> None:
    query_source = getsource(PostgresInsightRepository._workforce_rows)
    response_source = getsource(PostgresInsightRepository._workforce)

    assert "ARRAY_AGG(DISTINCT agg.site_code ORDER BY agg.site_code) AS site_codes" in query_source
    assert 'for site_code in (row["site_codes"] or ())' in response_source


def test_promo_and_incentive_slices_preserve_reconciled_mechanism_values() -> None:
    rows = [
        campaign_row("promo", "S1", "Mobiup", sales="100", quantity=10, reward="11.25"),
        campaign_row("promo", "S2", "MobiCell", sales="200", quantity=20, reward="22.75"),
        campaign_row("incentive", "S1", "Mobiup", sales="400", quantity=40, reward="30"),
        campaign_row("incentive", "S2", "MobiCell", sales="500", quantity=50, reward="45"),
    ]

    promo = PostgresInsightRepository._commercial_campaign_slice("promo", rows, "2026-06")  # type: ignore[arg-type]
    incentive = PostgresInsightRepository._commercial_campaign_slice("incentive", rows, "2026-06")  # type: ignore[arg-type]

    assert kpi_values(promo) == {
        "campaigns.promo_sales": Decimal("300.00"),
        "campaigns.promo_quantity": Decimal(30),
        "campaigns.promo_discount": Decimal("34.00"),
        "campaigns.promo_active_stores": Decimal(2),
        "campaigns.promo_active_products": Decimal(3),
        "campaigns.promo_qualifying_receipts": Decimal(4),
        "campaigns.promo_discounted_units": Decimal(30),
    }
    assert kpi_values(incentive) == {
        "campaigns.incentive_sales": Decimal("900.00"),
        "campaigns.incentive_quantity": Decimal(90),
        "campaigns.incentive_reward": Decimal("75.00"),
        "campaigns.incentive_active_stores": Decimal(2),
        "campaigns.incentive_active_products": Decimal(967),
        "campaigns.incentive_qualified_quantity": Decimal(86),
        "campaigns.incentive_eligible_quantity": Decimal(88),
    }
    assert len(promo.breakdown) == 2
    assert len(incentive.breakdown) == 2
    assert promo.alerts[0].id == "campaign-promo-partial"


def test_unpublished_campaign_slice_keeps_metrics_missing() -> None:
    promo = PostgresInsightRepository._commercial_campaign_slice("promo", [], "2026-07")

    assert promo.kpis == []
    assert promo.trend == []
    assert promo.alerts[0].id == "campaign-promo-missing"

    unavailable_row = campaign_row("promo", "S1", "Mobiup", sales="100", quantity=10, reward="5")
    unavailable_row["status"] = "unavailable"
    unavailable = PostgresInsightRepository._commercial_campaign_slice(  # type: ignore[arg-type]
        "promo", [unavailable_row], "2026-06"
    )
    assert unavailable.kpis == []


def test_promo_receipts_remain_absent_when_the_read_model_publishes_null() -> None:
    row = campaign_row("promo", "S1", "Mobiup", sales="100", quantity=10, reward="5")
    row["promo_qualifying_bons"] = None

    promo = kpi_values(
        PostgresInsightRepository._commercial_campaign_slice("promo", [row], "2026-06")  # type: ignore[arg-type]
    )

    assert "campaigns.promo_qualifying_receipts" not in promo


def test_folii_consumes_only_the_canonical_mechanism_variant() -> None:
    rows = [
        campaign_row(
            "promo",
            "S1",
            "Mobiup",
            sales="100",
            quantity=10,
            reward="5",
            mechanism_variant="same_model_screen_camera",
        ),
        campaign_row(
            "promo",
            "S2",
            "Mobiup",
            sales="200",
            quantity=20,
            reward="10",
            mechanism_variant="some_other_promo",
        ),
    ]

    folii = kpi_values(
        PostgresInsightRepository._commercial_campaign_slice(
            "promo",
            rows,
            "2026-06",
            metric_name="folii",
            mechanism_variant="same_model_screen_camera",
        )  # type: ignore[arg-type]
    )
    promo = kpi_values(
        PostgresInsightRepository._commercial_campaign_slice("promo", rows, "2026-06")  # type: ignore[arg-type]
    )

    assert folii["campaigns.folii_sales"] == Decimal("100.00")
    assert promo["campaigns.promo_sales"] == Decimal("200.00")
    assert "folii-ecran-camera-iunie" not in getsource(PostgresInsightRepository._campaigns)


def test_campaign_quantity_remains_net_when_returns_are_published() -> None:
    rows = [
        campaign_row("promo", "S1", "Mobiup", sales="100", quantity=10, reward="5"),
        campaign_row("promo", "S2", "Mobiup", sales="-20", quantity=-2, reward="0"),
    ]

    promo = kpi_values(
        PostgresInsightRepository._commercial_campaign_slice("promo", rows, "2026-06")  # type: ignore[arg-type]
    )

    assert promo["campaigns.promo_sales"] == Decimal("80.00")
    assert promo["campaigns.promo_quantity"] == Decimal(8)


def test_contest_slice_uses_exact_points_and_keeps_prize_textual() -> None:
    source = SourceMetadata(
        domain=SourceDomain.CONTEST,
        source="contest_reporting_heads",
        period="2026-06",
        authority="contest_reporting_head",
        status=SourceStatus.PARTIAL,
    )
    rows = [
        {
            "period": "2026-06",
            "contest_key": "iunie",
            "site_code": "S1",
            "agent": "Agent test",
            "locatie": "Magazin S1",
            "regional": "RM Test",
            "focus_units": 4,
            "promo_units": 3,
            "price_units": 2,
            "focus_points": 8,
            "promo_points": 6,
            "price_points": 5,
            "total_points": 19,
            "prize": "Premiu nivel 1",
            "rank": 1,
            "status": "partial",
            "warnings": [],
        }
    ]

    slice_ = PostgresInsightRepository._contest_slice(rows, "2026-06", source)  # type: ignore[arg-type]

    assert kpi_values(slice_) == {
        "campaigns.contest_points_total": Decimal(19),
        "campaigns.contest_focus_units": Decimal(4),
        "campaigns.contest_promo_units": Decimal(3),
        "campaigns.contest_price_units": Decimal(2),
        "campaigns.contest_focus_points": Decimal(8),
        "campaigns.contest_promo_points": Decimal(6),
        "campaigns.contest_price_points": Decimal(5),
    }
    assert slice_.breakdown[0].tertiary == Decimal(1)
    assert "Premiu nivel 1" in slice_.breakdown[0].context


def test_june_2026_representative_firm_slices_sum_to_retail_network_truth() -> None:
    promo_rows = [
        campaign_row(
            "promo",
            "MOBIUP",
            "Mobiup",
            sales="98880.60",
            quantity=526,
            reward="11664.26",
            qualifying=302,
            eligible=302,
            active_products=40,
        ),
        campaign_row(
            "promo",
            "MOBICELL",
            "MobiCell",
            sales="91663.98",
            quantity=564,
            reward="10326.82",
            qualifying=344,
            eligible=344,
            active_products=37,
            product_start=5,
        ),
    ]
    for row in promo_rows:
        row["promo_qualifying_bons"] = None
    incentive_rows = [
        campaign_row(
            "incentive",
            "MOBIUP",
            "Mobiup",
            sales="1371590.36",
            quantity=14006,
            reward="33105.00",
            qualifying=8289,
            eligible=13237,
            active_products=838,
        ),
        campaign_row(
            "incentive",
            "MOBICELL",
            "MobiCell",
            sales="1431768.62",
            quantity=15101,
            reward="43262.50",
            qualifying=9503,
            eligible=14312,
            active_products=809,
            product_start=68,
        ),
    ]

    promo = kpi_values(
        PostgresInsightRepository._commercial_campaign_slice("promo", promo_rows, "2026-06")  # type: ignore[arg-type]
    )
    incentive = kpi_values(
        PostgresInsightRepository._commercial_campaign_slice("incentive", incentive_rows, "2026-06")  # type: ignore[arg-type]
    )

    assert promo["campaigns.promo_sales"] == Decimal("190544.58")
    assert promo["campaigns.promo_quantity"] == Decimal(1090)
    assert promo["campaigns.promo_discount"] == Decimal("21991.08")
    assert "campaigns.promo_qualifying_receipts" not in promo
    assert promo["campaigns.promo_discounted_units"] == Decimal(646)
    assert promo["campaigns.promo_active_products"] == Decimal(42)
    assert incentive["campaigns.incentive_sales"] == Decimal("2803358.98")
    assert incentive["campaigns.incentive_quantity"] == Decimal(29107)
    assert incentive["campaigns.incentive_reward"] == Decimal("76367.50")
    assert incentive["campaigns.incentive_qualified_quantity"] == Decimal(17792)
    assert incentive["campaigns.incentive_eligible_quantity"] == Decimal(27549)
    assert incentive["campaigns.incentive_active_products"] == Decimal(877)
