from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient


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
    response = client.get(
        "/api/v1/exports/modules/sales.xlsx",
        params={"period": "2026-07"},
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


def test_unknown_export_section_is_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/exports/monthly-review.xlsx",
        params={"period": "2026-07", "section": "unknown"},
    )

    assert response.status_code == 422
