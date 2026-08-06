from fastapi.testclient import TestClient

from unihub_insight_api.config import Settings
from unihub_insight_api.main import create_app


def test_liveness_and_request_metadata(client: TestClient) -> None:
    response = client.get("/livez", headers={"X-Request-ID": "test-request-1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"] == "test-request-1"
    assert response.headers["server-timing"].startswith("app;dur=")


def test_demo_readiness(client: TestClient) -> None:
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "data_mode": "demo"}

    metric = client.get("/ready-metrics")
    assert metric.status_code == 200
    assert "unihub_insight_ready 1" in metric.text


def test_metrics_exposes_bounded_http_telemetry(client: TestClient) -> None:
    client.get("/livez")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "unihub_insight_http_requests_total" in response.text
    assert 'route="/livez"' in response.text
    assert 'source_sha="development"' in response.text
    assert 'traffic_class="system"' in response.text
    assert 'surface="system"' in response.text


def test_unhandled_exception_is_counted_as_http_5xx() -> None:
    app = create_app(Settings(environment="test", data_mode="demo"))

    async def boom() -> None:
        raise RuntimeError("expected test failure")

    app.add_api_route("/boom", boom)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")
        metrics = test_client.get("/metrics").text

    assert response.status_code == 500
    assert 'route="/boom",method="GET",status_class="5xx"' in metrics


def test_web_vital_uses_finite_surface_and_demo_traffic_class(client: TestClient) -> None:
    accepted = client.post(
        "/api/v1/telemetry/web-vital",
        json={
            "metric": "LCP",
            "value_ms": 1200,
            "rating": "good",
            "navigation_type": "navigate",
            "surface": "module-sales",
        },
    )
    rejected = client.post(
        "/api/v1/telemetry/web-vital",
        json={
            "metric": "LCP",
            "value_ms": 1200,
            "rating": "good",
            "surface": "user-controlled-cardinality",
        },
    )

    assert accepted.status_code == 204
    assert rejected.status_code == 422
    metrics = client.get("/metrics").text
    assert 'traffic_class="demo",surface="module-sales",metric="LCP"' in metrics
