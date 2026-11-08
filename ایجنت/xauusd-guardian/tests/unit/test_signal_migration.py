"""S5: migration 0003 is additive, history-preserving, and correct on a fresh DB."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone

import pytest

from guardian.storage.db import apply_migrations, connect, migration_history

START = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)


def test_fresh_database_applies_all_migrations(tmp_path, project_root):
    conn = connect(tmp_path / "fresh.sqlite3")
    applied = apply_migrations(conn, project_root / "migrations")

    assert applied == [1, 2, 3], applied
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"signal_runs", "signals"} <= tables
    history = migration_history(conn)
    assert [m.version for m in history] == [1, 2, 3]
    assert history[-1].filename == "0003_signals.sql"
    assert history[-1].sha256.startswith("sha256:")


def test_signals_primary_key_is_the_planned_one(tmp_path, project_root):
    conn = connect(tmp_path / "pk.sqlite3")
    apply_migrations(conn, project_root / "migrations")

    info = conn.execute("PRAGMA table_info(signals)").fetchall()
    primary_key = [row["name"] for row in sorted(info, key=lambda r: r["pk"]) if row["pk"]]
    assert primary_key == ["symbol", "timeframe", "bar_time_utc", "strategy_id"]


def test_strength_is_text_so_decimal_stays_exact(tmp_path, project_root):
    conn = connect(tmp_path / "types.sqlite3")
    apply_migrations(conn, project_root / "migrations")

    types = {row["name"]: row["type"] for row in conn.execute("PRAGMA table_info(signals)")}
    assert types["strength"] == "TEXT"


def test_signal_runs_carries_the_symbol(tmp_path, project_root):
    conn = connect(tmp_path / "runs.sqlite3")
    apply_migrations(conn, project_root / "migrations")

    columns = {row["name"] for row in conn.execute("PRAGMA table_info(signal_runs)")}
    assert {"run_id", "symbol", "strategy_id", "timeframe", "from_utc", "to_utc",
            "bars_seen", "signals", "written", "identical", "status", "created_utc"} <= columns


def test_migration_is_additive_and_keeps_existing_rows(tmp_path, project_root):
    legacy = tmp_path / "legacy_migrations"
    legacy.mkdir()
    for name in ("0001_init.sql", "0002_market_data.sql"):
        shutil.copy(project_root / "migrations" / name, legacy / name)

    conn = connect(tmp_path / "legacy.sqlite3")
    assert apply_migrations(conn, legacy) == [1, 2]

    conn.execute(
        "INSERT INTO feed_runs (run_id, symbol, kind, started_utc, status) VALUES (?,?,?,?,?)",
        ("run-old", "XAUUSD.", "bars", START.isoformat(), "OK"),
    )
    conn.execute(
        "INSERT INTO bars (symbol, timeframe, time_utc, open, high, low, close, tick_volume, "
        "spread_points, real_volume, content_sha256, first_seen_utc, last_seen_utc, run_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("XAUUSD.", "M5", START.isoformat(), 1.0, 2.0, 0.5, 1.5, 10, 0, 0.0, "sha", "x", "y", "run-old"),
    )
    conn.commit()

    assert apply_migrations(conn, project_root / "migrations") == [3]
    assert conn.execute("SELECT COUNT(*) AS c FROM bars").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) AS c FROM feed_runs").fetchone()["c"] == 1
    assert conn.execute("SELECT close FROM bars").fetchone()["close"] == 1.5
    assert [m.version for m in migration_history(conn)] == [1, 2, 3]


def test_applied_migration_is_hash_checked(tmp_path, project_root):
    """Editing an applied migration must be refused, not silently re-applied."""
    copy = tmp_path / "migrations"
    shutil.copytree(project_root / "migrations", copy)
    conn = connect(tmp_path / "hash.sqlite3")
    apply_migrations(conn, copy)

    target = copy / "0003_signals.sql"
    target.write_text(target.read_text(encoding="utf-8") + "\n-- tampered\n", encoding="utf-8")

    from guardian.storage.db import MigrationError

    with pytest.raises(MigrationError):
        apply_migrations(conn, copy)
