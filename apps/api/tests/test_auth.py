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


def test_proxy_metrics_count_only_verified_non_probe_subject_as_real() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="test-secret",
    )
    base_headers = {
        "X-UniHub-Proxy-Secret": "test-secret",
        "X-Authentik-Groups": "unihub-manager",
    }
    with TestClient(create_app(settings)) as proxy_client:
        assert (
            proxy_client.get(
                "/api/v1/overview?period=2026-08",
                headers={**base_headers, "X-Authentik-Uid": "andrei"},
            ).status_code
            == 200
        )
        assert (
            proxy_client.get(
                "/api/v1/overview?period=2026-08",
                headers={**base_headers, "X-Authentik-Uid": "insight-load-gate"},
            ).status_code
            == 200
        )
        rendered = proxy_client.get("/metrics").text

    assert 'traffic_class="real",surface="overview"' in rendered
    assert 'traffic_class="synthetic",surface="overview"' in rendered
    assert "andrei" not in rendered
    assert "insight-load-gate" not in rendered


def test_proxy_identity_parses_authentik_pipe_separated_groups() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="test-secret",
        analytics_groups="unihub-insight-access",
        management_groups="unihub-manager",
        hr_groups="unihub-hr",
        pnl_groups="unihub-pnl",
        admin_groups="unihub-admin",
    )
    with TestClient(create_app(settings)) as proxy_client:
        response = proxy_client.get(
            "/api/v1/me",
            headers={
                "X-UniHub-Proxy-Secret": "test-secret",
                "X-Authentik-Uid": "user-1",
                "X-Authentik-Groups": "unihub-insight-access|unihub-manager|unihub-hr",
            },
        )

    assert response.status_code == 200
    assert set(response.json()["capabilities"]) == {
        "insight:analytics",
        "insight:management",
        "insight:hr",
    }


def test_allowlisted_analytics_user_can_read_and_export_every_module() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="test-secret",
        analytics_groups="unihub-insight-access",
        management_groups="unihub-manager",
        hr_groups="unihub-hr",
        pnl_groups="unihub-pnl",
        admin_groups="unihub-admin",
    )
    headers = {
        "X-UniHub-Proxy-Secret": "test-secret",
        "X-Authentik-Uid": "allowlisted-user",
        "X-Authentik-Groups": "unihub-insight-access",
    }
    with TestClient(create_app(settings)) as proxy_client:
        for module in ("sales", "performance", "campaigns", "workforce", "compensation", "finance", "planning"):
            assert (
                proxy_client.get(
                    f"/api/v1/modules/{module}?period=2026-08",
                    headers=headers,
                ).status_code
                == 200
            )
        for module in ("compensation", "finance"):
            assert (
                proxy_client.get(
                    f"/api/v1/exports/modules/{module}.xlsx?period=2026-08",
                    headers=headers,
                ).status_code
                == 200
            )


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
