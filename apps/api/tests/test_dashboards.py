from fastapi.testclient import TestClient

from unihub_insight_api.config import Settings
from unihub_insight_api.main import create_app

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

    versions = client.get(f"/api/v1/dashboards/{created['id']}/versions")
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [2, 1]

    conflict = client.put(
        f"/api/v1/dashboards/{created['id']}",
        json=update_payload,
    )
    assert conflict.status_code == 409

    deleted = client.delete(f"/api/v1/dashboards/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/dashboards/{created['id']}").status_code == 404


def test_editor_cannot_reshare_or_delete_dashboard() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="secret",
    )
    owner = {
        "X-UniHub-Proxy-Secret": "secret",
        "X-Authentik-Uid": "owner",
        "X-Authentik-Groups": "unihub-manager",
    }
    editor = {
        "X-UniHub-Proxy-Secret": "secret",
        "X-Authentik-Uid": "editor",
        "X-Authentik-Groups": "unihub-manager",
    }
    body = {**PAYLOAD, "acl": [{"subject": "editor", "permission": "edit"}]}
    with TestClient(create_app(settings)) as client:
        created = client.post("/api/v1/dashboards", json=body, headers=owner).json()

        edited = client.put(
            f"/api/v1/dashboards/{created['id']}",
            json={**body, "name": "Editor update", "version": 1},
            headers=editor,
        )
        assert edited.status_code == 200

        reshared_body = {
            **body,
            "name": "Editor update",
            "version": 2,
            "acl": [
                {"subject": "editor", "permission": "edit"},
                {"subject": "third", "permission": "read"},
            ],
        }
        assert (
            client.put(
                f"/api/v1/dashboards/{created['id']}",
                json=reshared_body,
                headers=editor,
            ).status_code
            == 403
        )
        assert client.delete(f"/api/v1/dashboards/{created['id']}", headers=editor).status_code == 403
        assert client.delete(f"/api/v1/dashboards/{created['id']}", headers=owner).status_code == 204


def test_filter_preset_crud_and_optimistic_conflict(client: TestClient) -> None:
    created_response = client.post(
        "/api/v1/dashboards/presets",
        json={"name": "Brașov", "filters": {"regional": "Brașov"}, "shared": True},
    )
    assert created_response.status_code == 201
    created = created_response.json()

    listed = client.get("/api/v1/dashboards/presets")
    assert [item["id"] for item in listed.json()] == [created["id"]]

    update = {
        "name": "Brașov RM",
        "filters": {"regional": "Brașov"},
        "shared": False,
        "version": 1,
    }
    updated = client.put(f"/api/v1/dashboards/presets/{created['id']}", json=update)
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert client.put(f"/api/v1/dashboards/presets/{created['id']}", json=update).status_code == 409
    assert client.delete(f"/api/v1/dashboards/presets/{created['id']}").status_code == 204


def test_shared_dashboard_is_read_only_visible_without_acl_but_private_remains_hidden() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="secret",
    )
    owner = {
        "X-UniHub-Proxy-Secret": "secret",
        "X-Authentik-Uid": "owner",
        "X-Authentik-Groups": "unihub-manager",
    }
    reader = {
        "X-UniHub-Proxy-Secret": "secret",
        "X-Authentik-Uid": "reader",
        "X-Authentik-Groups": "unihub-manager",
    }
    with TestClient(create_app(settings)) as client:
        shared = client.post(
            "/api/v1/dashboards",
            json={**PAYLOAD, "name": "Shared", "visibility": "shared"},
            headers=owner,
        ).json()
        private = client.post(
            "/api/v1/dashboards",
            json={**PAYLOAD, "name": "Private"},
            headers=owner,
        ).json()

        listed = client.get("/api/v1/dashboards", headers=reader).json()["items"]
        assert [item["id"] for item in listed] == [shared["id"]]
        assert client.get(f"/api/v1/dashboards/{shared['id']}", headers=reader).status_code == 200
        assert client.get(f"/api/v1/dashboards/{private['id']}", headers=reader).status_code == 404
        denied_write = client.put(
            f"/api/v1/dashboards/{shared['id']}",
            json={**PAYLOAD, "visibility": "shared", "version": 1},
            headers=reader,
        )
        assert denied_write.status_code == 403
