from fastapi.testclient import TestClient


MODULES = (
    "sales",
    "performance",
    "campaigns",
    "workforce",
    "compensation",
    "finance",
    "planning",
)


def test_all_demo_modules_have_complete_analytical_surfaces(client: TestClient) -> None:
    for module in MODULES:
        response = client.get(
            f"/api/v1/modules/{module}",
            params={"period": "2026-08", "comparison": "previous-year"},
        )
        assert response.status_code == 200, module
        payload = response.json()
        assert payload["module"] == module
        assert len(payload["kpis"]) == 4
        assert len(payload["trend"]) == 12
        assert payload["distribution"]
        assert payload["breakdown"]
        assert payload["matrix"]
        assert payload["supported_charts"]
        assert payload["alerts"]


def test_module_response_is_deterministic(client: TestClient) -> None:
    params = {"period": "2026-08", "stores": "B001,B002"}
    first = client.get("/api/v1/modules/sales", params=params)
    second = client.get("/api/v1/modules/sales", params=params)
    assert first.status_code == 200
    assert first.json()["kpis"] == second.json()["kpis"]
    assert first.json()["trend"] == second.json()["trend"]


def test_unknown_module_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/modules/unknown", params={"period": "2026-08"})
    assert response.status_code == 422
