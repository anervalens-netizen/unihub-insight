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
