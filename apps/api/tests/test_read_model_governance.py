import inspect
from pathlib import Path

from fastapi.testclient import TestClient

from unihub_insight_api.config import Settings
from unihub_insight_api.main import create_app
from unihub_insight_api.repositories.postgres import PostgresAnalyticsRepository
from unihub_insight_api.repositories.postgres_modules import PostgresInsightRepository

ROOT = Path(__file__).resolve().parents[3]


def test_overview_snapshot_metadata_uses_only_the_governed_read_model() -> None:
    summary = inspect.getsource(PostgresAnalyticsRepository._fetch_summary)

    assert "reporting_source_snapshot_v7" in summary
    assert "import_snapshots" not in summary


def test_sensitive_modules_read_only_versioned_reporting_contracts() -> None:
    compensation = inspect.getsource(PostgresInsightRepository._compensation_rows)
    finance = inspect.getsource(PostgresInsightRepository._finance_rows)
    planning = inspect.getsource(PostgresInsightRepository._planning_rows)

    assert "reporting_compensation_person_month_v2" in compensation
    assert "salary_records" not in compensation
    assert "agent_salary_links" not in compensation
    assert "full_name" in compensation
    assert "person_id" in compensation

    assert "reporting_finance_month_v2" in finance
    assert "store_pnl_monthly" not in finance
    assert "store_pnl_generation_rows" not in finance

    assert "reporting_planning_scenario_v2" in planning
    assert "ai_forecast_runs" not in planning
    assert "target_scenarios" not in planning
    assert "scenario.metric = 'sales_value'" in planning
    assert "ROW_NUMBER() OVER" not in planning
    assert "forecast_run_id DESC" not in planning
    assert "scenario.status <> 'unavailable'" in planning
    assert 'alias="scenario"' in planning
    assert "target_contract_invalid" not in planning


def test_sales_calendar_reads_only_the_versioned_daily_contract() -> None:
    calendar = inspect.getsource(PostgresInsightRepository._sales_calendar)

    assert "reporting_sales_day_v1" in calendar
    assert "reporting_agent_day" not in calendar
    assert "reporting_item_day" not in calendar
    assert "sales_transactions" not in calendar


def test_visits_read_only_the_team_leader_v2_contract() -> None:
    visits = inspect.getsource(PostgresInsightRepository._visit_rows)

    assert "reporting_visit_month_v2" in visits
    assert "fieldops_visits" not in visits
    assert "visits_snapshot" not in visits
    assert "team_leader_id" in visits
    assert "team_leader_name" in visits


def test_commercial_campaigns_read_only_the_head_selected_v3_contract() -> None:
    campaigns = inspect.getsource(PostgresInsightRepository._campaign_mechanism_rows)

    assert "reporting_campaign_month_v3" in campaigns
    assert "campaign.mechanism_variant" in campaigns
    assert "campaign.agent" in campaigns
    assert "incentive_campaigns" not in campaigns
    assert "incentive_products" not in campaigns
    assert "reporting_item_day" not in campaigns
    assert "reporting_item_month" not in campaigns


def test_contest_and_grile_use_only_the_published_read_models() -> None:
    contest = inspect.getsource(PostgresInsightRepository._contest_rows)
    grile = inspect.getsource(PostgresInsightRepository._grile_slice)

    assert "reporting_contest_month_v1" in contest
    assert "qualifying_sales" not in contest
    assert "qualifying_quantity" not in contest
    assert "score" not in contest
    assert "contest.total_points" in contest
    assert "contest.prize" in contest
    assert "reporting_grile_month_v2" in grile
    assert "grile_store_current_status" not in grile


def test_compensation_accepts_person_store_and_agent_scope_and_export() -> None:
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

    assert module_response.status_code == 200
    assert export_response.status_code == 200


def test_bootstrap_uses_view_only_sensitive_acl_and_audit_is_append_only() -> None:
    roles = (ROOT / "ops/postgres/roles-before-migration.sql.template").read_text()
    migration = (ROOT / "apps/api/migrations/003_dashboard_acl_and_query_contract.sql").read_text()

    assert "reporting_compensation_month_v1" in roles
    assert "reporting_compensation_person_month_v2" in roles
    assert "reporting_compensation_month_v2" in roles
    assert "reporting_finance_month_v1" in roles
    assert "reporting_finance_month_v2" in roles
    assert "reporting_planning_scenario_v1" in roles
    assert "reporting_planning_scenario_v2" in roles
    assert "reporting_sales_day_v1" in roles
    assert "reporting_source_snapshot_v2" in roles
    assert "reporting_source_snapshot_v3" in roles
    assert "reporting_source_snapshot_v4" in roles
    assert "reporting_source_snapshot_v6" in roles
    assert "reporting_source_snapshot_v7" in roles
    assert "reporting_visit_month_v2" in roles
    assert "reporting_campaign_month_v2" in roles
    assert "reporting_campaign_month_v3" in roles
    assert "reporting_contest_month_v1" in roles
    assert "reporting_grile_month_v2" in roles
    assert "'fieldops_visits'" in roles
    assert "ON TABLE salary_records" not in roles
    assert "ON TABLE agent_salary_links" not in roles
    assert "store_pnl_monthly," not in roles
    assert "ai_forecast_runs," not in roles
    assert "GRANT INSERT ON TABLE insight.query_audit" in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE insight.query_audit" not in migration


def test_widget_xlsx_audit_migration_remains_append_only() -> None:
    migration = (ROOT / "apps/api/migrations/004_query_audit_xlsx.sql").read_text()

    assert "'export.xlsx'" in migration
    assert "'export.module.xlsx'" in migration
    assert "GRANT" not in migration
