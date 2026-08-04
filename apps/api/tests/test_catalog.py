from fastapi.testclient import TestClient

from unihub_insight_api.services import METRIC_CATALOG


def test_metric_catalog_ids_are_unique() -> None:
    ids = [metric.id for metric in METRIC_CATALOG]
    assert len(ids) == len(set(ids))
    assert all(metric.version >= 1 for metric in METRIC_CATALOG)


def test_metric_catalog_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/catalog/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert {item["id"] for item in payload} == {metric.id for metric in METRIC_CATALOG}
    assert all(item["allowed_dimensions"] for item in payload)
