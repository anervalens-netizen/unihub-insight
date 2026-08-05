from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_role_bootstrap_uses_isolated_authorities_and_owner() -> None:
    sql = (ROOT / "ops/postgres/roles-before-migration.sql.template").read_text(encoding="utf-8")

    for role in (
        "unihub_insight_reader",
        "unihub_insight_metadata",
        "unihub_insight_migrator",
        "unihub_insight_schema_owner",
    ):
        assert f"CREATE ROLE {role}\n    NOLOGIN" in sql
    assert "CREATE SCHEMA insight AUTHORIZATION unihub_insight_schema_owner" in sql
    assert "GRANT CONNECT, CREATE ON DATABASE" not in sql
    assert "CREATE ON SCHEMA public" not in sql
    assert "GRANT CONNECT ON DATABASE unihub TO unihub_insight_migration_runner" in sql
    assert "REVOKE TEMPORARY ON DATABASE unihub FROM" not in sql
    assert "GRANT SELECT ON TABLE sales_transactions TO unihub_insight_reader" not in sql
    assert "reporting_compensation_month_v1" in sql
    assert "salary_records" not in sql
    assert "agent_salary_links" not in sql
    assert "person_id" not in sql


def test_metadata_authority_is_limited_to_dashboards() -> None:
    migration = (ROOT / "apps/api/migrations/001_insight_metadata.sql").read_text(encoding="utf-8")
    compatibility = (ROOT / "ops/postgres/metadata-grants-after-migration.sql").read_text(encoding="utf-8")

    assert "CREATE SCHEMA" not in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE insight.dashboards" in migration
    assert "ON ALL TABLES IN SCHEMA insight" not in compatibility
    assert "ALTER DEFAULT PRIVILEGES" not in compatibility


def test_metadata_backup_and_restore_enter_only_the_insight_schema_owner() -> None:
    for script_name in ("backup-metadata.sh", "restore-metadata.sh"):
        script = (ROOT / "ops/scripts" / script_name).read_text(encoding="utf-8")
        assert "--role=unihub_insight_schema_owner" in script


def test_readiness_is_private_and_rollback_checks_migration_compatibility_first() -> None:
    caddy = (ROOT / "ops/caddy/unihub-insight.caddy.template").read_text(encoding="utf-8")
    rollback = (ROOT / "ops/scripts/rollback.sh").read_text(encoding="utf-8")
    deploy = (ROOT / "ops/scripts/deploy-release.sh").read_text(encoding="utf-8")

    assert "@insight_diagnostics path /livez /readyz /metrics /ready-metrics" in caddy
    assert "handle /ready-metrics {\n\t\treverse_proxy unix//run/unihub-insight/api.sock" in caddy
    assert rollback.index("check-release-migrations.sh") < rollback.index('ln -sfn "$RELEASE"')
    assert "previous release is incompatible with applied metadata migrations" in deploy
