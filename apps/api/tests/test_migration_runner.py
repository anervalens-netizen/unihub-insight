from pathlib import Path

from ops.scripts.migrate import checksum, migration_files, transactional_sql


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
