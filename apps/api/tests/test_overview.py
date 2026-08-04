from fastapi.testclient import TestClient


def test_filter_options_contract(client: TestClient) -> None:
    response = client.get("/api/v1/filters/options", params={"period": "2026-08"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_mode"] == "demo"
    assert "2026-08" in payload["periods"]
    assert payload["firms"] == sorted(payload["firms"])
    assert len(payload["stores"]) >= 10
    assert len(payload["agents"]) >= 20


def test_overview_contract_and_future_actual_gaps(client: TestClient) -> None:
    response = client.get(
        "/api/v1/overview",
        params={"period": "2026-08", "comparison": "previous-year"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["period"] == "2026-08"
    assert payload["meta"]["data_mode"] == "demo"
    assert len(payload["kpis"]) == 4
    assert len(payload["daily"]) == 31
    assert payload["daily"][-1]["sales"] is None
    assert payload["daily"][-1]["forecast"] is not None
    assert payload["performance"]


def test_store_scope_is_deduplicated_and_deterministic(client: TestClient) -> None:
    params = {
        "period": "2026-08",
        "stores": "B001,B002,B001",
        "firm": "MOBICELL",
    }
    first = client.get("/api/v1/overview", params=params)
    second = client.get("/api/v1/overview", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["meta"]["scope_label"] == "2 magazine"
    assert {row["id"] for row in first_payload["performance"]} == {"B001", "B002"}
    assert first_payload["kpis"] == second_payload["kpis"]
    assert first_payload["daily"] == second_payload["daily"]


def test_invalid_period_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/overview", params={"period": "2026-13"})

    assert response.status_code == 422
