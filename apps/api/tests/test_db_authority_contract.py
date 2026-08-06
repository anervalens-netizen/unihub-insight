import hashlib
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
    reader_grant = sql.split("GRANT SELECT ON TABLE", 1)[1].split("TO unihub_insight_reader;", 1)[0]
    assert "salary_records" not in reader_grant
    assert "agent_salary_links" not in reader_grant
    assert "person_id" not in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.%I FROM unihub_insight_reader" in sql
    for raw_source in (
        "sales_transactions",
        "import_snapshots",
        "salary_records",
        "store_pnl_monthly",
        "store_pnl_generation_rows",
        "ai_forecast_runs",
        "target_scenarios",
    ):
        assert f"'{raw_source}'" in sql


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


def test_metadata_backup_publishes_an_atomic_verified_offhost_copy() -> None:
    script = (ROOT / "ops/scripts/backup-metadata.sh").read_text(encoding="utf-8")
    unit = (ROOT / "ops/systemd/unihub-insight-backup.service").read_text(encoding="utf-8")
    deploy = (ROOT / "ops/scripts/deploy-release.sh").read_text(encoding="utf-8")

    assert "OFFHOST_PARTIAL" in script
    assert 'mv -f "$OFFHOST_PARTIAL" "$OFFHOST_FILE"' in script
    assert "off-host backup checksum mismatch" in script
    assert "RequiresMountsFor=/mnt/nas" in unit
    assert "/mnt/nas/backups/server-68/unihub-insight" in unit
    assert deploy.count("systemctl start unihub-insight-backup.service") == 2


def test_isolated_restore_drill_is_fail_closed_and_dependency_complete() -> None:
    script = (ROOT / "ops/scripts/verify-metadata-backup.sh").read_text(encoding="utf-8")

    assert "--schema-only --exclude-schema=insight" in script
    assert "pg_restore" in script and "--exit-on-error" in script
    assert "refusing existing restore database" in script
    assert "trap cleanup_restore EXIT" in script
    assert "SELECT MAX(version) FROM insight.schema_migrations" in script


def test_readiness_is_private_and_rollback_checks_migration_compatibility_first() -> None:
    caddy = (ROOT / "ops/caddy/unihub-insight.caddy.template").read_text(encoding="utf-8")
    rollback = (ROOT / "ops/scripts/rollback.sh").read_text(encoding="utf-8")
    compatibility = (ROOT / "ops/scripts/check-release-migrations.sh").read_text(encoding="utf-8")
    deploy = (ROOT / "ops/scripts/deploy-release.sh").read_text(encoding="utf-8")

    assert "@insight_diagnostics path /livez /readyz /metrics /ready-metrics" in caddy
    assert "handle /ready-metrics {\n\t\treverse_proxy unix//run/unihub-insight/api.sock" in caddy
    assert rollback.index("check-release-migrations.sh") < rollback.index('ln -sfn "$RELEASE"')
    assert "SET ROLE unihub_insight_schema_owner" in compatibility
    assert "--quiet --tuples-only --no-align" in compatibility
    assert "previous release is incompatible with applied metadata migrations" in deploy


def test_rollback_compatibility_allowlist_pins_the_exact_additive_migration() -> None:
    migration = ROOT / "apps/api/migrations/004_query_audit_xlsx.sql"
    manifest = (ROOT / "ops/rollback-compatible-migrations.txt").read_text(encoding="utf-8")
    compatibility = (ROOT / "ops/scripts/check-release-migrations.sh").read_text(encoding="utf-8")
    checksum = hashlib.sha256(migration.read_bytes()).hexdigest()

    assert f"004_query_audit_xlsx.sql|{checksum}|" in manifest
    assert 'compatible_checksum" == "$expected_checksum' in compatibility
    assert "target release accepts backward-compatible applied migration" in compatibility


def test_forward_schema_runner_survives_code_rollback() -> None:
    unit = (ROOT / "ops/systemd/unihub-insight-migrate.service").read_text(encoding="utf-8")
    deploy = (ROOT / "ops/scripts/deploy-release.sh").read_text(encoding="utf-8")
    preflight = (ROOT / "ops/scripts/preflight.sh").read_text(encoding="utf-8")
    rollback = (ROOT / "ops/scripts/rollback.sh").read_text(encoding="utf-8")

    assert "WorkingDirectory=/opt/unihub-insight/schema-current" in unit
    assert "ExecStart=/opt/unihub-insight/schema-current/apps/api/.venv/bin/python" in unit
    assert 'SCHEMA_CURRENT="$BASE/schema-current"' in deploy
    assert deploy.index("unihub-insight-backup.service") < deploy.index("MIGRATION_MAY_HAVE_STARTED=true")
    assert '"$SCHEMA_RELEASE/apps/api/.venv/bin/python" ops/scripts/migrate.py --check' in preflight
    assert "schema-current" not in rollback
