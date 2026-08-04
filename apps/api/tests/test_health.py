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
