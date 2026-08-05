import inspect
from pathlib import Path

from fastapi.testclient import TestClient

from unihub_insight_api.config import Settings
from unihub_insight_api.main import create_app
from unihub_insight_api.repositories.postgres_modules import PostgresInsightRepository

ROOT = Path(__file__).resolve().parents[3]


def test_sensitive_modules_read_only_versioned_reporting_contracts() -> None:
    compensation = inspect.getsource(PostgresInsightRepository._compensation_rows)
    finance = inspect.getsource(PostgresInsightRepository._finance_rows)
    planning = inspect.getsource(PostgresInsightRepository._planning_rows)

    assert "reporting_compensation_month_v1" in compensation
    assert "salary_records" not in compensation
    assert "agent_salary_links" not in compensation
    assert "full_name" not in compensation
    assert "person_id" not in compensation

    assert "reporting_finance_month_v1" in finance
    assert "store_pnl_monthly" not in finance
    assert "store_pnl_generation_rows" not in finance

    assert "reporting_planning_scenario_v1" in planning
    assert "ai_forecast_runs" not in planning
    assert "target_scenarios" not in planning


def test_compensation_rejects_direct_differentiating_scope_and_export() -> None:
    settings = Settings(
        environment="test",
        data_mode="demo",
        auth_mode="proxy",
        trusted_proxy_secret="secret",
    )
    headers = {
        "X-UniHub-Proxy-Secret": "secret",
        "X-Authentik-Uid": "hr-user",
        "X-Authentik-Groups": "unihub-hr",
    }
    with TestClient(create_app(settings)) as client:
        module_response = client.get(
            "/api/v1/modules/compensation",
            params={"period": "2026-08", "stores": "BV001"},
            headers=headers,
        )
        export_response = client.get(
            "/api/v1/exports/modules/compensation.xlsx",
            params={"period": "2026-08", "agent": "private"},
            headers=headers,
        )

    assert module_response.status_code == 422
    assert export_response.status_code == 422


def test_bootstrap_uses_view_only_sensitive_acl_and_audit_is_append_only() -> None:
    roles = (ROOT / "ops/postgres/roles-before-migration.sql.template").read_text()
    migration = (ROOT / "apps/api/migrations/003_dashboard_acl_and_query_contract.sql").read_text()

    assert "reporting_compensation_month_v1" in roles
    assert "reporting_finance_month_v1" in roles
    assert "reporting_planning_scenario_v1" in roles
    assert "ON TABLE salary_records" not in roles
    assert "ON TABLE agent_salary_links" not in roles
    assert "store_pnl_monthly," not in roles
    assert "ai_forecast_runs," not in roles
    assert "GRANT INSERT ON TABLE insight.query_audit" in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE insight.query_audit" not in migration
