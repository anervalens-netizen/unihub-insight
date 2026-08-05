from fastapi.testclient import TestClient

from unihub_insight_api.config import Settings
from unihub_insight_api.main import create_app


def test_demo_identity_has_all_capabilities(client: TestClient) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "demo-admin"
    assert payload["is_demo"] is True
    assert "insight:pnl" in payload["capabilities"]


def test_proxy_identity_requires_trusted_boundary() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="test-secret",
    )
    with TestClient(create_app(settings)) as proxy_client:
        denied = proxy_client.get("/api/v1/me")
        assert denied.status_code == 401

        allowed = proxy_client.get(
            "/api/v1/me",
            headers={
                "X-UniHub-Proxy-Secret": "test-secret",
                "X-Authentik-Uid": "user-1",
                "X-Authentik-Email": "user@example.com",
                "X-Authentik-Groups": "unihub-manager",
            },
        )
        assert allowed.status_code == 200
        payload = allowed.json()
        assert payload["subject"] == "user-1"
        assert set(payload["capabilities"]) == {
            "insight:analytics",
            "insight:management",
        }


def test_admin_group_does_not_bypass_hr_or_pnl_group_configuration() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="test-secret",
        analytics_groups="unihub-admin",
        management_groups="unihub-admin",
        hr_groups="unihub-hr",
        pnl_groups="unihub-pnl",
        admin_groups="unihub-admin",
    )
    with TestClient(create_app(settings)) as proxy_client:
        response = proxy_client.get(
            "/api/v1/me",
            headers={
                "X-UniHub-Proxy-Secret": "test-secret",
                "X-Authentik-Uid": "admin-1",
                "X-Authentik-Groups": "unihub-admin",
            },
        )

    assert response.status_code == 200
    assert set(response.json()["capabilities"]) == {
        "insight:analytics",
        "insight:management",
        "insight:admin",
    }
