from decimal import Decimal
from inspect import getsource
from types import SimpleNamespace

import pytest

from unihub_insight_api.domain import Capability, ChartKind, UserContext, WidgetQuery
from unihub_insight_api.repositories.postgres_modules import PostgresInsightRepository
from unihub_insight_api.services.metric_catalog import METRIC_CATALOG
from unihub_insight_api.services.query_planner import QueryValidationFailure, _dataset, _metric_for

NETWORK_SALES = Decimal("3223513.13")
NETWORK_QUANTITY = Decimal("33279")


def portfolio_row(
    identifier: str,
    label: str,
    *,
    sales: Decimal,
    quantity: Decimal,
    returns: Decimal = Decimal(0),
    receipt_incidence: Decimal = Decimal(0),
    label_variants: int = 1,
    attribute_variants: int = 1,
) -> dict[str, object]:
    return {
        "id": identifier,
        "label": label,
        "context": f"Context {identifier}",
        "total_sales": sales,
        "net_quantity": quantity,
        "return_quantity": returns,
        "receipt_count": receipt_incidence,
        "label_variants": label_variants,
        "attribute_variants": attribute_variants,
    }


def metric_values(slice_: object) -> dict[str, Decimal]:
    return {metric.id: metric.value for metric in slice_.kpis}  # type: ignore[attr-defined]


def test_category_and_subcategory_slices_conserve_network_sales_and_quantity() -> None:
    category_rows = [
        portfolio_row("audio", "Audio", sales=Decimal("2000000.00"), quantity=Decimal("21000")),
        portfolio_row("cases", "Huse", sales=Decimal("1223513.13"), quantity=Decimal("12279")),
    ]
    subcategory_rows = [
        portfolio_row("audio:buds", "Buds", sales=Decimal("1800000.00"), quantity=Decimal("19000")),
        portfolio_row("audio:cables", "Cabluri", sales=Decimal("200000.00"), quantity=Decimal("2000")),
        portfolio_row("cases:phone", "Telefon", sales=Decimal("1223513.13"), quantity=Decimal("12279")),
    ]

    for dimension, rows in (("category", category_rows), ("subcategory", subcategory_rows)):
        slice_ = PostgresInsightRepository._portfolio_slice(
            dimension=dimension,
            rows=rows,
            item_detail=False,
        )
        values = metric_values(slice_)
        assert values["sales.portfolio_sales"] == NETWORK_SALES
        assert values["sales.portfolio_net_quantity"] == NETWORK_QUANTITY
        assert slice_.entity_dimension == dimension
        assert slice_.distribution_dimension == dimension


def test_product_slice_preserves_signed_returns_and_only_exposes_sku_receipt_incidence() -> None:
    rows = [
        portfolio_row(
            "sku-1",
            "Produs 1",
            sales=Decimal("2000000.00"),
            quantity=Decimal("21000"),
            returns=Decimal("-41"),
            receipt_incidence=Decimal("20500"),
        ),
        portfolio_row(
            "sku-2",
            "Produs 2",
            sales=Decimal("1223513.13"),
            quantity=Decimal("12279"),
            returns=Decimal("-17"),
            receipt_incidence=Decimal("11900"),
        ),
    ]
    product = PostgresInsightRepository._portfolio_slice(
        dimension="product",
        rows=rows,
        item_detail=True,
        include_receipt_incidence=True,
    )
    brand = PostgresInsightRepository._portfolio_slice(
        dimension="brand",
        rows=rows,
        item_detail=True,
    )

    values = metric_values(product)
    assert values["sales.portfolio_sales"] == NETWORK_SALES
    assert values["sales.portfolio_net_quantity"] == NETWORK_QUANTITY
    assert values["sales.portfolio_return_quantity"] == Decimal("-58")
    assert values["sales.portfolio_receipt_incidence"] == Decimal("32400")
    assert product.breakdown[0].tertiary == Decimal("-41")
    assert product.breakdown[0].quaternary == Decimal("20500")
    assert product.supported_charts == (ChartKind.KPI, ChartKind.TABLE)
    assert ChartKind.DONUT in brand.supported_charts
    assert "sales.portfolio_receipt_incidence" not in metric_values(brand)
    assert all(row.quaternary is None for row in brand.breakdown)
    assert next(axis.label for axis in product.axes if axis.key == "tertiary") == "Cantitate retur semnată"
    assert next(axis.label for axis in product.axes if axis.key == "quaternary") == "Incidențe SKU în bonuri"


def test_product_identity_is_strictly_sku_and_conflicts_are_visible_without_losing_totals() -> None:
    source = getsource(PostgresInsightRepository._portfolio_item_rows)
    assert 'grouping = "scoped.item_code"' in source
    assert 'label = "MAX(scoped.item_name)"' in source
    assert "COUNT(DISTINCT scoped.item_name)" in source
    assert "brand_group" not in source

    product = PostgresInsightRepository._portfolio_slice(
        dimension="product",
        rows=[
            portfolio_row(
                "SKU-100",
                "Denumire stabilă",
                sales=Decimal("100.00"),
                quantity=Decimal("3"),
                label_variants=2,
                attribute_variants=2,
            )
        ],
        item_detail=True,
        include_receipt_incidence=True,
    )
    assert [row.id for row in product.breakdown] == ["SKU-100"]
    assert metric_values(product)["sales.portfolio_sales"] == Decimal("100.00")
    assert any(alert.id == "portfolio-product-identity-conflict" for alert in product.alerts)


def test_non_positive_portfolio_rows_remain_in_total_and_raise_share_context_alert() -> None:
    slice_ = PostgresInsightRepository._portfolio_slice(
        dimension="product",
        rows=[
            portfolio_row("positive", "Pozitiv", sales=Decimal("100.00"), quantity=Decimal("4")),
            portfolio_row("return-only", "Retur", sales=Decimal("-20.00"), quantity=Decimal("-1")),
        ],
        item_detail=True,
        include_receipt_incidence=True,
    )

    assert metric_values(slice_)["sales.portfolio_sales"] == Decimal("80.00")
    assert [item.id for item in slice_.distribution] == ["positive"]
    alert = next(item for item in slice_.alerts if item.id == "portfolio-product-non-positive-sales")
    assert "vânzări nete pozitive" in alert.description
    assert len(slice_.breakdown) == 2


def test_product_table_keeps_return_only_rows_context_and_receipt_incidence() -> None:
    product = PostgresInsightRepository._portfolio_slice(
        dimension="product",
        rows=[
            portfolio_row(
                "positive",
                "Pozitiv",
                sales=Decimal("100.00"),
                quantity=Decimal("4"),
                returns=Decimal("-1"),
                receipt_incidence=Decimal("3"),
            ),
            portfolio_row(
                "return-only",
                "Retur",
                sales=Decimal("-20.00"),
                quantity=Decimal("-1"),
                returns=Decimal("-2"),
                receipt_incidence=Decimal("1"),
            ),
        ],
        item_detail=True,
        include_receipt_incidence=True,
    )
    query = WidgetQuery(
        widget_id="product-table",
        module="sales",
        metric_id="sales.portfolio_return_quantity",
        dimensions=("product",),
        visualization=ChartKind.TABLE,
    )
    dataset = _dataset(query, SimpleNamespace(portfolio={"product": product}))

    assert {item.id for item in dataset.dimensions} >= {"context", "tertiary", "quaternary"}
    returned = next(row for row in dataset.rows if row["id"] == "return-only")
    assert returned["context"] == "Context return-only"
    assert returned["value"] == Decimal("-2")
    assert returned["quaternary"] == Decimal("1")


def test_receipt_incidence_catalog_is_product_only_and_never_claims_distinct_receipts() -> None:
    catalog = {metric.id: metric for metric in METRIC_CATALOG}
    incidence = catalog["sales.portfolio_receipt_incidence"]
    assert incidence.allowed_dimensions == ("product",)
    assert "bonuri distincte" in incidence.description
    assert "sales.portfolio_receipt_count" not in catalog


def test_product_portfolio_rejects_high_cardinality_distribution() -> None:
    query = WidgetQuery(
        widget_id="portfolio-products",
        module="sales",
        metric_id="sales.portfolio_sales",
        dimensions=("product",),
        visualization=ChartKind.DONUT,
    )
    user = UserContext(subject="owner", capabilities=frozenset({Capability.ANALYTICS}))

    with pytest.raises(QueryValidationFailure, match="numai KPI și tabel"):
        _metric_for(query, user)
