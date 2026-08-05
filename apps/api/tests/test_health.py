from fastapi.testclient import TestClient


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
