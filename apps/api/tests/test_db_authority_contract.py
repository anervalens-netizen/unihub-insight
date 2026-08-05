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
    assert "GRANT SELECT (\n    year, month, person_id" in sql
    assert "GRANT SELECT (\n    person_id, agent_code, match_status" in sql


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
