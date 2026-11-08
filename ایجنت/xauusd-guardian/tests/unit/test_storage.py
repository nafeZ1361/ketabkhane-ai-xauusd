from __future__ import annotations

import shutil
import sqlite3

import pytest

from guardian.storage.db import (
    MigrationError,
    apply_migrations,
    connect,
    discover_migrations,
    migration_history,
)


def test_migrations_apply_once(project_root, tmp_path):
    db = connect(tmp_path / "guardian.sqlite3")
    try:
        applied = apply_migrations(db, project_root / "migrations")
        assert applied == [1, 2, 3]

        again = apply_migrations(db, project_root / "migrations")
        assert again == []

        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"symbol_snapshots", "risk_decisions", "audit_events", "schema_migrations"} <= tables
        assert len(migration_history(db)) == 3
    finally:
        db.close()


def test_migration_discovery_is_sorted(project_root):
    files = discover_migrations(project_root / "migrations")
    assert [f.name for f in files] == ["0001_init.sql", "0002_market_data.sql", "0003_signals.sql"]


def test_tampered_migration_is_detected(project_root, tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    target = migrations / "0001_init.sql"
    shutil.copy(project_root / "migrations" / "0001_init.sql", target)

    db = connect(tmp_path / "guardian.sqlite3")
    try:
        apply_migrations(db, migrations)
        target.write_text(target.read_text(encoding="utf-8") + "\n-- tampered\n", encoding="utf-8")
        with pytest.raises(MigrationError, match="changed after being applied"):
            apply_migrations(db, migrations)
    finally:
        db.close()


def test_missing_migrations_dir_is_not_an_error(tmp_path):
    db = connect(tmp_path / "guardian.sqlite3")
    try:
        assert apply_migrations(db, tmp_path / "absent") == []
    finally:
        db.close()


def test_foreign_keys_and_wal_are_enabled(tmp_path):
    db = connect(tmp_path / "guardian.sqlite3")
    try:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        db.close()


def test_symbol_snapshot_requires_columns(tmp_path, project_root):
    db = connect(tmp_path / "guardian.sqlite3")
    apply_migrations(db, project_root / "migrations")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO symbol_snapshots (symbol) VALUES ('XAUUSD.')")
    finally:
        db.close()
