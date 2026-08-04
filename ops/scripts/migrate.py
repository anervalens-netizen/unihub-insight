#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
from pathlib import Path

import asyncpg


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "apps" / "api" / "migrations"
LOCK_NAME = "unihub-insight-migrations-v1"
VERSION_PATTERN = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")
BOOTSTRAP_SQL = """
CREATE SCHEMA IF NOT EXISTS insight;
CREATE TABLE IF NOT EXISTS insight.schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migration_files() -> list[Path]:
    files = sorted(
        path for path in MIGRATIONS.glob("*.sql") if VERSION_PATTERN.fullmatch(path.name)
    )
    if not files:
        raise RuntimeError(f"No migrations found in {MIGRATIONS}")
    versions = [path.name.split("_", 1)[0] for path in files]
    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate migration version detected")
    return files


def transactional_sql(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    cleaned = [
        line for line in lines if line.strip().upper() not in {"BEGIN;", "COMMIT;"}
    ]
    return "\n".join(cleaned).strip()


async def check_existing(connection: asyncpg.Connection, files: list[Path]) -> None:
    exists = await connection.fetchval(
        "SELECT to_regclass('insight.schema_migrations') IS NOT NULL"
    )
    if not exists:
        raise RuntimeError("Insight migration registry does not exist")
    rows = await connection.fetch(
        "SELECT version, checksum FROM insight.schema_migrations"
    )
    recorded = {str(row["version"]): str(row["checksum"]) for row in rows}
    expected = {path.name: checksum(path) for path in files}
    unknown = sorted(set(recorded) - set(expected))
    missing = sorted(set(expected) - set(recorded))
    mismatched = sorted(
        name for name in expected if recorded.get(name) not in {None, expected[name]}
    )
    if unknown:
        raise RuntimeError(f"Unknown applied migrations: {', '.join(unknown)}")
    if missing:
        raise RuntimeError(f"Pending migrations: {', '.join(missing)}")
    if mismatched:
        raise RuntimeError(
            f"Immutable migration checksum mismatch: {', '.join(mismatched)}"
        )


async def apply(connection: asyncpg.Connection, files: list[Path]) -> None:
    await connection.execute("SELECT pg_advisory_lock(hashtext($1))", LOCK_NAME)
    try:
        await connection.execute(BOOTSTRAP_SQL)
        rows = await connection.fetch(
            "SELECT version, checksum FROM insight.schema_migrations"
        )
        recorded = {str(row["version"]): str(row["checksum"]) for row in rows}
        expected_names = {path.name for path in files}
        unknown = sorted(set(recorded) - expected_names)
        if unknown:
            raise RuntimeError(
                f"Database contains unknown migrations: {', '.join(unknown)}"
            )
        for path in files:
            digest = checksum(path)
            current = recorded.get(path.name)
            if current and current != digest:
                raise RuntimeError(
                    f"Checksum mismatch for immutable migration {path.name}"
                )
            if current:
                print(f"verified {path.name} {digest[:12]}")
                continue
            async with connection.transaction():
                await connection.execute(transactional_sql(path))
                await connection.execute(
                    "INSERT INTO insight.schema_migrations(version, checksum) VALUES($1, $2)",
                    path.name,
                    digest,
                )
            print(f"applied {path.name} {digest[:12]}")
    finally:
        await connection.execute(
            "SELECT pg_advisory_unlock(hashtext($1))", LOCK_NAME
        )


async def run(check_only: bool) -> None:
    dsn = os.environ.get("UNIHUB_INSIGHT_MIGRATION_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("UNIHUB_INSIGHT_MIGRATION_DATABASE_URL is required")
    files = migration_files()
    connection = await asyncpg.connect(
        dsn,
        command_timeout=35,
        server_settings={
            "application_name": "unihub-insight-migrator",
            "timezone": "UTC",
        },
    )
    try:
        if check_only:
            await check_existing(connection, files)
            print(f"verified {len(files)} applied migrations")
        else:
            await apply(connection, files)
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply immutable UniHub Insight metadata migrations"
    )
    parser.add_argument("--check", action="store_true", help="verify without writes")
    arguments = parser.parse_args()
    asyncio.run(run(arguments.check))


if __name__ == "__main__":
    main()
