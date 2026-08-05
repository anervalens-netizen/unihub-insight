from pathlib import Path

import pytest
from ops.scripts.migrate import (
    SCHEMA_OWNER_ROLE,
    activate_schema_owner,
    apply,
    checksum,
    migration_files,
    transactional_sql,
)


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> None:
        return None


class _Connection:
    def __init__(self, *, active_owner: bool = True) -> None:
        self.active_owner = active_owner
        self.commands: list[str] = []

    async def execute(self, query: str, *_: object) -> None:
        self.commands.append(query)

    async def fetchval(self, query: str, *_: object) -> bool:
        self.commands.append(query)
        return self.active_owner

    async def fetch(self, query: str, *_: object) -> list[object]:
        self.commands.append(query)
        return []

    def transaction(self) -> _Transaction:
        return _Transaction()


def test_migrations_are_ordered_and_uniquely_versioned() -> None:
    files = migration_files()
    assert files == sorted(files)
    assert len({path.name.split("_", 1)[0] for path in files}) == len(files)
    assert all(len(checksum(path)) == 64 for path in files)


def test_transaction_wrapper_is_owned_by_runner(tmp_path: Path) -> None:
    migration = tmp_path / "001_example.sql"
    migration.write_text(
        "BEGIN;\nCREATE TABLE example(id INT);\nCOMMIT;\n",
        encoding="utf-8",
    )
    assert transactional_sql(migration) == "CREATE TABLE example(id INT);"


@pytest.mark.asyncio
async def test_schema_owner_activation_is_transaction_local() -> None:
    connection = _Connection()

    await activate_schema_owner(connection)  # type: ignore[arg-type]

    assert connection.commands == [
        f"SET LOCAL ROLE {SCHEMA_OWNER_ROLE}",
        "SELECT current_user = $1",
    ]


@pytest.mark.asyncio
async def test_schema_owner_activation_fails_closed() -> None:
    connection = _Connection(active_owner=False)

    with pytest.raises(RuntimeError, match="schema-owner elevation failed"):
        await activate_schema_owner(connection)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_apply_activates_schema_owner_for_bootstrap_and_each_migration(tmp_path: Path) -> None:
    migrations = []
    for version in ("001", "002"):
        path = tmp_path / f"{version}_example.sql"
        path.write_text("BEGIN;\nSELECT 1;\nCOMMIT;\n", encoding="utf-8")
        migrations.append(path)
    connection = _Connection()

    await apply(connection, migrations)  # type: ignore[arg-type]

    assert connection.commands.count(f"SET LOCAL ROLE {SCHEMA_OWNER_ROLE}") == 4
    assert all("CREATE SCHEMA" not in command for command in connection.commands)
