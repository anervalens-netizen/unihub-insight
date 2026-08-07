from fastapi.testclient import TestClient

from unihub_insight_api.config import Settings
from unihub_insight_api.main import create_app

BASE_WIDGET = {
    "id": "sales-kpi",
    "module": "sales",
    "title": "Vânzări",
    "metric_id": "sales.total",
    "visualization": "kpi",
    "filter_mode": "inherit",
    "filters": {},
    "options": {},
    "layout": {"x": 0, "y": 0, "w": 6, "h": 4, "min_w": 4, "min_h": 3},
}


def payload(widget: dict[str, object]) -> dict[str, object]:
    return {"name": "Test", "description": "", "visibility": "private", "widgets": [widget]}


def test_rejects_unknown_metric_and_canvas_overflow(client: TestClient) -> None:
    widget = {
        **BASE_WIDGET,
        "metric_id": "finance.revenue",
        "layout": {**BASE_WIDGET["layout"], "x": 22, "w": 6},
    }
    response = client.post("/api/v1/dashboards", json=payload(widget))
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("not registered" in item for item in errors)
    assert any("24-column" in item for item in errors)


def test_rejects_duplicate_widget_ids(client: TestClient) -> None:
    body = payload(BASE_WIDGET)
    body["widgets"] = [BASE_WIDGET, BASE_WIDGET]
    response = client.post("/api/v1/dashboards", json=body)
    assert response.status_code == 422


def test_authenticated_manager_can_save_finance_widget() -> None:
    settings = Settings(environment="test", data_mode="demo", auth_mode="proxy", trusted_proxy_secret="secret")
    headers = {
        "X-UniHub-Proxy-Secret": "secret",
        "X-Authentik-Uid": "manager",
        "X-Authentik-Groups": "unihub-manager",
    }
    widget = {**BASE_WIDGET, "module": "finance", "metric_id": "finance.revenue"}
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/dashboards", json=payload(widget), headers=headers)
    assert response.status_code == 201


def test_ignore_mode_cannot_hide_embedded_filters(client: TestClient) -> None:
    widget = {**BASE_WIDGET, "filter_mode": "ignore", "filters": {"firm": "MOBIUP"}}
    response = client.post("/api/v1/dashboards", json=payload(widget))
    assert response.status_code == 422


def test_dashboard_accepts_two_ordered_dimensions_and_keeps_legacy_alias(client: TestClient) -> None:
    widget = {
        **BASE_WIDGET,
        "module": "performance",
        "metric_id": "performance.average",
        "visualization": "heatmap",
        "dimension": "store",
        "dimensions": ["store", "time"],
    }
    response = client.post("/api/v1/dashboards", json=payload(widget))

    assert response.status_code == 201
    saved = response.json()["widgets"][0]
    assert saved["dimension"] == "store"
    assert saved["dimensions"] == ["store", "time"]


def test_dashboard_rejects_two_dimensions_when_the_shape_does_not_consume_them(
    client: TestClient,
) -> None:
    widget = {
        **BASE_WIDGET,
        "visualization": "table",
        "dimension": "store",
        "dimensions": ["store", "time"],
    }

    response = client.post("/api/v1/dashboards", json=payload(widget))

    assert response.status_code == 422
    assert any("two dimensions require heatmap" in item for item in response.json()["detail"]["errors"])


def test_dashboard_rejects_a_divergent_legacy_dimension_alias(client: TestClient) -> None:
    widget = {
        **BASE_WIDGET,
        "module": "performance",
        "metric_id": "performance.average",
        "visualization": "heatmap",
        "dimension": "asm",
        "dimensions": ["store", "time"],
    }
    response = client.post("/api/v1/dashboards", json=payload(widget))

    assert response.status_code == 422
    assert any("legacy alias" in item for item in response.json()["detail"]["errors"])


def test_dashboard_validates_presentation_option_types_and_bounds(client: TestClient) -> None:
    invalid = {
        **BASE_WIDGET,
        "limit": 10,
        "options": {"show_labels": "yes", "top_n": 11, "pixel_ratio": True},
    }
    response = client.post("/api/v1/dashboards", json=payload(invalid))

    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("requires booleans" in item for item in errors)
    assert any("top_n" in item for item in errors)
    assert any("pixel_ratio" in item for item in errors)

    valid = {
        **BASE_WIDGET,
        "limit": 10,
        "options": {"show_labels": True, "top_n": 5, "pixel_ratio": 2},
    }
    assert client.post("/api/v1/dashboards", json=payload(valid)).status_code == 201


def test_dashboard_accepts_only_the_daily_sales_calendar_contract(client: TestClient) -> None:
    valid = {
        **BASE_WIDGET,
        "visualization": "calendar",
        "dimension": "time",
        "dimensions": ["time"],
        "time_grain": "day",
    }
    assert client.post("/api/v1/dashboards", json=payload(valid)).status_code == 201

    invalid = {**valid, "time_grain": "month"}
    response = client.post("/api/v1/dashboards", json=payload(invalid))
    assert response.status_code == 422
    assert any("calendar requires" in item for item in response.json()["detail"]["errors"])


def test_dashboard_validates_sales_portfolio_taxonomy_dimensions(client: TestClient) -> None:
    product = {
        **BASE_WIDGET,
        "metric_id": "sales.portfolio_receipt_incidence",
        "dimension": "product",
        "dimensions": ["product"],
    }
    assert client.post("/api/v1/dashboards", json=payload(product)).status_code == 201

    invalid = {**product, "dimension": "brand", "dimensions": ["brand"]}
    response = client.post("/api/v1/dashboards", json=payload(invalid))
    assert response.status_code == 422
    assert any("incompatible" in item for item in response.json()["detail"]["errors"])
