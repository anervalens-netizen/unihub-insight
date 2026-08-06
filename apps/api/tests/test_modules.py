from fastapi.testclient import TestClient

from unihub_insight_api.domain import SourceStatus

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


def test_module_range_and_simultaneous_comparisons_are_applied(client: TestClient) -> None:
    response = client.get(
        "/api/v1/modules/sales",
        params={
            "period": "2026-08",
            "range": "3",
            "comparisons": "target,previous-period,previous-year,recent-average",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["key"] for item in payload["trend"]] == ["2026-06", "2026-07", "2026-08"]
    assert payload["meta"]["range_start"] == "2026-06"
    assert payload["meta"]["range_end"] == "2026-08"
    assert payload["meta"]["requested_comparisons"] == [
        "target",
        "previous-period",
        "previous-year",
        "recent-average",
    ]
    assert not payload["meta"]["warnings"]
    assert all(
        comparison in payload["trend"][-1]["comparisons"]
        for comparison in ("previous-period", "previous-year", "recent-average")
    )


def test_native_module_uses_primary_metric_comparison_allowlist(client: TestClient) -> None:
    response = client.get(
        "/api/v1/modules/performance",
        params={"period": "2026-08", "range": "3", "comparisons": "target,previous-year"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["requested_comparisons"] == ["previous-year"]
    assert payload["meta"]["warnings"] == ["Comparații ignorate de allowlist-ul metricii native: target."]
    assert all("target" not in point["comparisons"] for point in payload["trend"])


def test_custom_range_must_end_at_the_common_period(client: TestClient) -> None:
    response = client.get(
        "/api/v1/modules/sales",
        params={"period": "2026-08", "range": "custom", "start": "2026-01", "end": "2026-07"},
    )

    assert response.status_code == 422


def test_unknown_module_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/modules/unknown", params={"period": "2026-08"})
    assert response.status_code == 422


def test_native_module_does_not_fetch_an_unavailable_source(client: TestClient) -> None:
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
    response = client.get("/api/v1/modules/finance", params={"period": "2026-08"})

    assert response.status_code == 200
    assert finance_fetches == 0
    payload = response.json()
    assert payload["kpis"] == []
    assert payload["meta"]["sources"]["finance"]["status"] == "unavailable"
    assert payload["alerts"][0]["id"] == "finance-source-unavailable"


def test_campaigns_declares_sales_denominator_and_does_not_fetch_without_it(
    client: TestClient,
) -> None:
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
    response = client.get("/api/v1/modules/campaigns", params={"period": "2026-08"})

    assert response.status_code == 200
    assert campaign_fetches == 0
    payload = response.json()
    assert payload["kpis"] == []
    assert payload["meta"]["sources"]["sales"]["status"] == "unavailable"
    assert payload["alerts"][0]["id"] == "campaigns-source-unavailable"
