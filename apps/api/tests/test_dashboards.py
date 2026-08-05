from fastapi.testclient import TestClient

PAYLOAD = {
    "name": "Director",
    "description": "Dashboard executiv",
    "visibility": "private",
    "widgets": [
        {
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
    ],
}


def test_dashboard_crud_and_optimistic_conflict(client: TestClient) -> None:
    created_response = client.post("/api/v1/dashboards", json=PAYLOAD)
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["version"] == 1

    listed = client.get("/api/v1/dashboards")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [created["id"]]

    update_payload = {**PAYLOAD, "name": "Director v2", "version": 1}
    updated_response = client.put(
        f"/api/v1/dashboards/{created['id']}",
        json=update_payload,
    )
    assert updated_response.status_code == 200
    assert updated_response.json()["version"] == 2

    conflict = client.put(
        f"/api/v1/dashboards/{created['id']}",
        json=update_payload,
    )
    assert conflict.status_code == 409

    deleted = client.delete(f"/api/v1/dashboards/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/dashboards/{created['id']}").status_code == 404
