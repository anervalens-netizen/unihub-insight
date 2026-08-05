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
        assert len(payload["kpis"]) >= 4
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


def test_module_range_is_applied_and_unsupported_comparisons_are_explicit(client: TestClient) -> None:
    response = client.get(
        "/api/v1/modules/sales",
        params={
            "period": "2026-08",
            "range": "3",
            "comparisons": "target,recent-average",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["key"] for item in payload["trend"]] == ["2026-06", "2026-07", "2026-08"]
    assert payload["meta"]["range_start"] == "2026-06"
    assert payload["meta"]["range_end"] == "2026-08"
    assert payload["meta"]["requested_comparisons"] == ["target", "recent-average"]
    assert "recent-average" in payload["meta"]["warnings"][0]


def test_custom_range_must_end_at_the_common_period(client: TestClient) -> None:
    response = client.get(
        "/api/v1/modules/sales",
        params={"period": "2026-08", "range": "custom", "start": "2026-01", "end": "2026-07"},
    )

    assert response.status_code == 422


def test_unknown_module_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/modules/unknown", params={"period": "2026-08"})
    assert response.status_code == 422
