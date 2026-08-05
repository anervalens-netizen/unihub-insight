from fastapi.testclient import TestClient

from unihub_insight_api.api.routes.query import _safe_csv_value


def widget(
    widget_id: str,
    module: str = "sales",
    metric_id: str = "sales.total",
    visualization: str = "line",
    dimensions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "widget_id": widget_id,
        "module": module,
        "metric_id": metric_id,
        "metric_version": 1,
        "query_contract_version": 1,
        "dimensions": dimensions or ["time"],
        "time_grain": "month",
        "filters": {},
        "comparisons": ["previous-year", "target"],
        "sort": [],
        "limit": 30,
        "visualization": visualization,
    }


def test_versioned_catalog_exposes_query_and_dimension_contract(client: TestClient) -> None:
    response = client.get("/api/v1/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 1
    assert payload["query_contract"]["max_widgets"] == 12
    assert {item["id"] for item in payload["dimensions"]} >= {"time", "store", "agent"}
    sales = next(item for item in payload["metrics"] if item["id"] == "sales.total")
    assert sales["version"] == 1
    assert sales["source_authority"] == "unihub-retail"
    assert "scatter" not in sales["allowed_shapes"]
    assert "treemap" in sales["allowed_shapes"]


def test_batch_reuses_one_snapshot_and_isolates_invalid_widget(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={
            "widgets": [
                widget("sales"),
                widget("invalid", metric_id="finance.ebit"),
                widget(
                    "finance",
                    module="finance",
                    metric_id="finance.ebit",
                    visualization="line",
                ),
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["id"].startswith("demo-2026-08-")
    by_id = {item["widget_id"]: item for item in payload["results"]}
    assert by_id["sales"]["meta"]["snapshot_id"] == payload["snapshot"]["id"]
    assert by_id["finance"]["meta"]["snapshot_id"] == payload["snapshot"]["id"]
    assert by_id["invalid"]["error"]["code"] == "invalid-query"
    assert by_id["sales"]["dataset"]["rows"]


def test_scatter_uses_explicit_business_axes(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={
            "widgets": [
                widget(
                    "performance-relation",
                    module="performance",
                    metric_id="performance.average",
                    visualization="scatter",
                    dimensions=["store"],
                )
            ]
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["error"] is None
    dimensions = {item["id"]: item["label"] for item in result["dataset"]["dimensions"]}
    assert dimensions["x"] == "Productivitate / zi-agent"
    assert dimensions["y"] == "Realizare target"
    assert result["dataset"]["rows"]


def test_waterfall_dataset_carries_reconciliation_roles(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={
            "widgets": [
                widget(
                    "finance-bridge",
                    module="finance",
                    metric_id="finance.ebit",
                    visualization="waterfall",
                    dimensions=["category"],
                )
            ]
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["error"] is None
    assert result["dataset"]["rows"][0]["step_kind"] == "start"
    assert result["dataset"]["rows"][-1]["step_kind"] == "total"


def test_batch_fails_closed_when_snapshot_changes_during_execution(client: TestClient) -> None:
    repository = client.app.state.analytics_repository
    original = repository.resolve_snapshot
    calls = 0

    async def changing_snapshot(scope):
        nonlocal calls
        calls += 1
        snapshot = await original(scope)
        return snapshot if calls == 1 else snapshot.model_copy(update={"id": f"{snapshot.id}-promoted"})

    repository.resolve_snapshot = changing_snapshot
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [widget("sales")]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == "Snapshot is no longer eligible."


def test_batch_is_bounded_to_twelve_widgets(client: TestClient) -> None:
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [widget(f"widget-{index}") for index in range(13)]},
    )

    assert response.status_code == 422


def test_inspect_requires_and_reuses_the_same_snapshot(client: TestClient) -> None:
    batch = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [widget("sales", visualization="table", dimensions=["store"])]},
    ).json()
    query = batch["results"][0]["query"]
    response = client.post(
        "/api/v1/query/inspect",
        params={"period": "2026-08"},
        json={
            "snapshot_id": batch["snapshot"]["id"],
            "query": query,
            "page": 1,
            "page_size": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["id"] == batch["snapshot"]["id"]
    assert len(payload["dataset"]["rows"]) <= 5
    assert payload["total_rows"] >= len(payload["dataset"]["rows"])


def test_compensation_rejects_differentiating_filter(client: TestClient) -> None:
    body = widget(
        "salary",
        module="compensation",
        metric_id="compensation.payroll",
        visualization="table",
        dimensions=["time"],
    )
    body["filters"] = {"agent": "private"}
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [body]},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["error"]["code"] == "invalid-query"


def test_csv_export_reuses_snapshot_carries_metadata_and_is_audited(client: TestClient) -> None:
    batch = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [widget("sales-table", visualization="table", dimensions=["store"])]},
    ).json()
    response = client.post(
        "/api/v1/query/export.csv",
        params={"period": "2026-08"},
        json={
            "snapshot_id": batch["snapshot"]["id"],
            "query": batch["results"][0]["query"],
            "page": 1,
            "page_size": 5,
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert "unihub-insight-sales-table-2026-08.csv" in response.headers["content-disposition"]
    content = response.content.decode("utf-8-sig")
    assert "_analytical_snapshot_id" in content
    assert batch["snapshot"]["id"] in content
    store = client.app.state.dashboard_store
    assert store._query_audit[-1]["action"] == "export.csv"
    assert store._query_audit[-1]["row_count"] <= 5


def test_csv_formula_injection_is_neutralized() -> None:
    assert _safe_csv_value("=SUM(A1:A2)") == "'=SUM(A1:A2)"
    assert _safe_csv_value("@cmd") == "'@cmd"
    assert _safe_csv_value(-7) == -7


def test_batch_rejects_a_time_range_outside_the_common_snapshot(client: TestClient) -> None:
    query = widget("history")
    query["time_range"] = {"start": "2026-01", "end": "2026-07"}
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [query]},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["error"]["code"] == "invalid-query"


def test_dashboard_ceiling_applies_to_widget_filter_overrides(client: TestClient) -> None:
    dashboard = client.post(
        "/api/v1/dashboards",
        json={
            "name": "Scoped",
            "scope_ceiling": {"stores": ["S001"]},
            "widgets": [
                {
                    "id": "sales",
                    "module": "sales",
                    "title": "Sales",
                    "metric_id": "sales.total",
                    "visualization": "line",
                    "dimension": "time",
                    "time_grain": "month",
                    "limit": 30,
                    "layout": {"x": 0, "y": 0, "w": 6, "h": 4},
                }
            ],
        },
    ).json()
    query = widget("sales")
    query["filters"] = {"stores": ["S002"]}
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08", "stores": "S001"},
        json={"dashboard_id": dashboard["id"], "widgets": [query]},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Widget scope exceeds dashboard ceiling."
