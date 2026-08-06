from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from unihub_insight_api.domain import SourceStatus


def assert_xlsx(content: bytes) -> None:
    assert content.startswith(b"PK")
    with ZipFile(BytesIO(content)) as archive:
        names = set(archive.namelist())
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names


def test_overview_export_is_a_real_workbook(client: TestClient) -> None:
    response = client.get(
        "/api/v1/exports/overview.xlsx",
        params={"period": "2026-07"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert_xlsx(response.content)
    assert client.app.state.dashboard_store._query_audit[-1]["action"] == "export.overview.xlsx"


def test_monthly_report_can_export_one_numeric_section(client: TestClient) -> None:
    response = client.get(
        "/api/v1/exports/monthly-review.xlsx",
        params={
            "period": "2026-07",
            "recent_months": 6,
            "section": "stores",
        },
    )

    assert response.status_code == 200
    assert_xlsx(response.content)
    assert client.app.state.dashboard_store._query_audit[-1]["action"] == "export.monthly.xlsx"


def test_module_export_is_audited_and_carries_snapshot_metadata(client: TestClient) -> None:
    module = client.get("/api/v1/modules/sales", params={"period": "2026-07"}).json()
    response = client.get(
        "/api/v1/exports/modules/sales.xlsx",
        params={
            "period": "2026-07",
            "snapshot_id": module["meta"]["analytical_snapshot_id"],
        },
    )

    assert response.status_code == 200
    assert_xlsx(response.content)
    with ZipFile(BytesIO(response.content)) as archive:
        xml = b"".join(archive.read(name) for name in archive.namelist() if name.endswith(".xml"))
        assert b"Snapshot analitic" in xml
        assert b"Surs" in xml
    audit = client.app.state.dashboard_store._query_audit[-1]
    assert audit["action"] == "export.module.xlsx"
    assert audit["widget_id"] == "module:sales"


def test_module_export_does_not_fetch_an_unavailable_source(client: TestClient) -> None:
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
    response = client.get(
        "/api/v1/exports/modules/finance.xlsx",
        params={"period": "2026-07"},
    )

    assert response.status_code == 409
    assert finance_fetches == 0
    assert "finance" in response.json()["detail"]


def test_module_export_rejects_a_stale_ui_snapshot_before_fetch(client: TestClient) -> None:
    repository = client.app.state.analytics_repository
    original_get_module = repository.get_module
    module_fetches = 0

    async def counted_get_module(module, scope):
        nonlocal module_fetches
        module_fetches += 1
        return await original_get_module(module, scope)

    repository.get_module = counted_get_module
    response = client.get(
        "/api/v1/exports/modules/sales.xlsx",
        params={"period": "2026-07", "snapshot_id": "stale-snapshot"},
    )

    assert response.status_code == 409
    assert module_fetches == 0


def test_unknown_export_section_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/exports/monthly-review.xlsx",
        params={"period": "2026-07", "section": "unknown"},
    )

    assert response.status_code == 422
