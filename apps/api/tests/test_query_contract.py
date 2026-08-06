import runpy
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from unihub_insight_api.api.routes.query import _safe_csv_value
from unihub_insight_api.domain import SourceStatus

ROOT = Path(__file__).resolve().parents[3]


def widget(
    widget_id: str,
    module: str = "sales",
    metric_id: str = "sales.total",
    visualization: str = "line",
    dimensions: list[str] | None = None,
) -> dict[str, object]:
    resolved_dimensions = dimensions if dimensions is not None else ["time"]
    return {
        "widget_id": widget_id,
        "module": module,
        "metric_id": metric_id,
        "metric_version": 1,
        "query_contract_version": 1,
        "dimensions": resolved_dimensions,
        "time_grain": "month",
        "filters": {},
        "comparisons": ["previous-year"] if "time" in resolved_dimensions else [],
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
    formula_references = [item["formula_reference"] for item in payload["metrics"]]
    assert len(formula_references) == len(set(formula_references))
    assert all(reference != "retail-reporting-contract" for reference in formula_references)


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


def test_calendar_returns_only_observed_daily_rows_with_return_and_coverage_context(
    client: TestClient,
) -> None:
    query = widget(
        "sales-calendar",
        metric_id="sales.total",
        visualization="calendar",
        dimensions=["time"],
    )
    query["time_grain"] = "day"
    query["comparisons"] = []
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [query]},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["error"] is None
    dimensions = {item["id"]: item for item in result["dataset"]["dimensions"]}
    assert dimensions["date"]["kind"] == "time"
    assert dimensions["return_quantity"]["role"] == "metadata"
    assert dimensions["observed_store_count"]["role"] == "metadata"
    rows = result["dataset"]["rows"]
    assert rows
    assert all(row["coverage_state"] == "observed" for row in rows)
    assert all(Decimal(str(row["return_quantity"])) <= 0 for row in rows)
    assert len({row["date"] for row in rows}) == len(rows)


def test_composed_pace_and_forecast_queries_preserve_inspect_parity(client: TestClient) -> None:
    pace = widget(
        "sales-pace",
        metric_id="target.progress_pct",
        visualization="kpi",
        dimensions=[],
    )
    pace["comparisons"] = []
    forecast = widget(
        "planning-forecast",
        module="planning",
        metric_id="planning.forecast",
        visualization="line",
    )
    forecast["comparisons"] = ["target"]
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [pace, forecast]},
    )

    assert response.status_code == 200
    pace_result, forecast_result = response.json()["results"]
    assert pace_result["error"] is None
    assert {"value", "actual", "target", "gap"} <= set(pace_result["dataset"]["rows"][0])
    assert forecast_result["error"] is None
    forecast_dimensions = {item["id"] for item in forecast_result["dataset"]["dimensions"]}
    assert {"value", "actual", "target"} <= forecast_dimensions


def test_query_rejects_two_dimensions_when_the_shape_does_not_consume_them(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [widget("invalid-2d", visualization="table", dimensions=["store", "time"])]},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["error"]["code"] == "invalid-query"
    assert "Două dimensiuni" in result["error"]["message"]


def test_trend_returns_all_requested_comparisons_in_one_dataset(client: TestClient) -> None:
    query = widget("sales-comparisons")
    query["comparisons"] = ["target", "previous-period", "previous-year", "recent-average"]
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [query]},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["error"] is None
    dimensions = {item["id"]: item["role"] for item in result["dataset"]["dimensions"]}
    assert {
        "previous_period": "comparison",
        "previous_year": "comparison",
        "recent_average": "comparison",
        "target": "target",
    }.items() <= dimensions.items()
    assert any(
        row["previous_period"] is not None and row["previous_year"] is not None and row["recent_average"] is not None
        for row in result["dataset"]["rows"]
    )


def test_metric_comparison_allowlist_rejects_semantically_empty_forecast(client: TestClient) -> None:
    query = widget("sales-forecast")
    query["comparisons"] = ["forecast"]
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [query]},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["error"]["code"] == "invalid-query"


def test_planning_actual_exposes_only_its_approved_forecast_comparison(client: TestClient) -> None:
    query = widget(
        "planning-actual-forecast",
        module="planning",
        metric_id="planning.actual",
        visualization="line",
    )
    query["comparisons"] = ["forecast"]
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [query]},
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["error"] is None
    assert any(dimension["id"] == "forecast" for dimension in result["dataset"]["dimensions"])
    assert any(row["forecast"] is not None for row in result["dataset"]["rows"])


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


def test_batch_does_not_query_an_unavailable_source(client: TestClient) -> None:
    repository = client.app.state.analytics_repository
    original_resolve = repository.resolve_snapshot
    original_get_module = repository.get_module
    finance_fetches = 0

    async def unavailable_finance(scope):
        snapshot = await original_resolve(scope)
        finance = snapshot.sources["finance"].model_copy(update={"status": SourceStatus.UNAVAILABLE})
        return snapshot.model_copy(update={"sources": {**snapshot.sources, "finance": finance}})

    async def counted_get_module(module, scope):
        nonlocal finance_fetches
        if module.value == "finance":
            finance_fetches += 1
        return await original_get_module(module, scope)

    repository.resolve_snapshot = unavailable_finance
    repository.get_module = counted_get_module
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={
            "widgets": [
                widget(
                    "finance",
                    module="finance",
                    metric_id="finance.ebit",
                    visualization="line",
                )
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["error"]["code"] == "unavailable"
    assert finance_fetches == 0


def test_campaign_query_requires_sales_denominator_source(client: TestClient) -> None:
    repository = client.app.state.analytics_repository
    original_resolve = repository.resolve_snapshot
    original_get_module = repository.get_module
    campaign_fetches = 0

    async def unavailable_sales(scope):
        snapshot = await original_resolve(scope)
        sales = snapshot.sources["sales"].model_copy(update={"status": SourceStatus.UNAVAILABLE})
        return snapshot.model_copy(update={"sources": {**snapshot.sources, "sales": sales}})

    async def counted_get_module(module, scope):
        nonlocal campaign_fetches
        if module.value == "campaigns":
            campaign_fetches += 1
        return await original_get_module(module, scope)

    repository.resolve_snapshot = unavailable_sales
    repository.get_module = counted_get_module
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={
            "widgets": [
                widget(
                    "campaign-share",
                    module="campaigns",
                    metric_id="campaigns.focus_share",
                    visualization="line",
                )
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["error"]["code"] == "unavailable"
    assert campaign_fetches == 0


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


def test_cross_domain_metrics_publish_all_source_provenance(client: TestClient) -> None:
    query = widget(
        "sales-ratio",
        module="compensation",
        metric_id="compensation.sales_ratio",
        visualization="kpi",
        dimensions=[],
    )
    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [query]},
    )

    assert response.status_code == 200
    meta = response.json()["results"][0]["meta"]
    assert set(meta["sources"]) == {"compensation", "sales"}

    planning_query = widget(
        "planning-forecast",
        module="planning",
        metric_id="planning.forecast",
        visualization="kpi",
        dimensions=[],
    )
    planning = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [planning_query]},
    ).json()["results"][0]
    assert set(planning["meta"]["sources"]) == {"planning", "sales"}


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
    assert "_coverage_numerator" in content
    assert "_contract_version" in content
    assert "_rule_version" in content
    assert batch["snapshot"]["id"] in content
    store = client.app.state.dashboard_store
    assert store._query_audit[-1]["action"] == "export.csv"
    assert store._query_audit[-1]["row_count"] == len(batch["results"][0]["dataset"]["rows"])


def test_xlsx_export_reuses_snapshot_carries_metadata_and_is_audited(client: TestClient) -> None:
    batch = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json={"widgets": [widget("sales-table", visualization="table", dimensions=["store"])]},
    ).json()
    response = client.post(
        "/api/v1/query/export.xlsx",
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
    assert "unihub-insight-sales-table-2026-08.xlsx" in response.headers["content-disposition"]
    with ZipFile(BytesIO(response.content)) as workbook:
        names = set(workbook.namelist())
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/worksheets/sheet2.xml" in names
        xml = b"".join(workbook.read(name) for name in names if name.endswith(".xml"))
        assert batch["snapshot"]["id"].encode() in xml
        assert b"sales.total" in xml
        assert b"coverage num" in xml
        assert b"contract version" in xml
        assert b"rule version" in xml
    store = client.app.state.dashboard_store
    assert store._query_audit[-1]["action"] == "export.xlsx"
    assert store._query_audit[-1]["row_count"] == len(batch["results"][0]["dataset"]["rows"])


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


def test_production_load_fixture_stays_valid_against_the_metric_catalog(client: TestClient) -> None:
    load_gate = runpy.run_path(str(ROOT / "ops/scripts/load-gate.py"))
    payload = load_gate["mixed_dashboard"]()

    response = client.post(
        "/api/v1/query/batch",
        params={"period": "2026-08"},
        json=payload,
    )

    assert response.status_code == 200
    errors = [result["error"] for result in response.json()["results"] if result["error"]]
    assert all(error["code"] == "unavailable" for error in errors)


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
