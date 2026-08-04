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
    widget = {**BASE_WIDGET, "metric_id": "finance.revenue", "layout": {**BASE_WIDGET["layout"], "x": 22, "w": 6}}
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


def test_manager_cannot_save_finance_widget() -> None:
    settings = Settings(environment="test", data_mode="demo", auth_mode="proxy", trusted_proxy_secret="secret")
    headers = {"X-UniHub-Proxy-Secret": "secret", "X-Authentik-Uid": "manager", "X-Authentik-Groups": "unihub-manager"}
    widget = {**BASE_WIDGET, "module": "finance", "metric_id": "finance.revenue"}
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/dashboards", json=payload(widget), headers=headers)
    assert response.status_code == 403


def test_ignore_mode_cannot_hide_embedded_filters(client: TestClient) -> None:
    widget = {**BASE_WIDGET, "filter_mode": "ignore", "filters": {"firm": "MOBIUP"}}
    response = client.post("/api/v1/dashboards", json=payload(widget))
    assert response.status_code == 422
