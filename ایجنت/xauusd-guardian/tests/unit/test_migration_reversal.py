"""S6: migration 0003 is additive and reversible, by execution rather than by text."""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import datetime, timezone

import pytest

from guardian.storage.db import (
    MigrationError,
    apply_migrations,
    connect,
    discover_down_migrations,
    discover_migrations,
    migration_history,
    reversal_plan,
    revert_migration,
)

START = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
BAR_COLUMNS = (
    "symbol, timeframe, time_utc, open, high, low, close, tick_volume, "
    "spread_points, real_volume, content_sha256, first_seen_utc, last_seen_utc, run_id"
)
OWNED_INDEXES = {"idx_signals_run", "idx_signal_runs_window"}


def seed_pre_0003(conn) -> None:
    """Rows that exist before 0003 is applied and must survive a reversal."""
    conn.execute(
        "INSERT INTO feed_runs (run_id, symbol, kind, started_utc, status) VALUES (?,?,?,?,?)",
        ("run-keep", "XAUUSD.", "bars", START.isoformat(), "OK"),
    )
    conn.execute(
        f"INSERT INTO bars ({BAR_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("XAUUSD.", "M5", START.isoformat(), 1.0, 2.0, 0.5, 1.5, 10, 0, 0.0, "sha", "x", "y", "run-keep"),
    )
    conn.commit()


def pre_0003_snapshot(conn) -> tuple[int, int, float]:
    return (
        conn.execute("SELECT COUNT(*) AS c FROM bars").fetchone()["c"],
        conn.execute("SELECT COUNT(*) AS c FROM feed_runs").fetchone()["c"],
        conn.execute("SELECT close FROM bars").fetchone()["close"],
    )


def table_names(conn) -> set[str]:
    return {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def index_names(conn) -> set[str]:
    return {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}


def legacy_dir(tmp_path, project_root):
    """A migrations directory containing only what existed before 0003."""
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    for name in ("0001_init.sql", "0002_market_data.sql"):
        shutil.copy(project_root / "migrations" / name, legacy / name)
    return legacy


def prepared_db(tmp_path, project_root, name: str):
    """A database at 0001+0002 with pre-0003 rows, then 0003 applied."""
    conn = connect(tmp_path / name)
    assert apply_migrations(conn, legacy_dir(tmp_path, project_root)) == [1, 2]
    seed_pre_0003(conn)
    assert apply_migrations(conn, project_root / "migrations") == [3]
    return conn


def test_revert_removes_only_the_0003_objects(tmp_path, project_root):
    conn = connect(tmp_path / "revert.sqlite3")
    assert apply_migrations(conn, legacy_dir(tmp_path, project_root)) == [1, 2]
    seed_pre_0003(conn)
    before = pre_0003_snapshot(conn)

    assert apply_migrations(conn, project_root / "migrations") == [3]
    assert {"signals", "signal_runs"} <= table_names(conn)

    assert revert_migration(conn, project_root / "migrations", 3) == 3

    remaining = table_names(conn)
    assert "signals" not in remaining
    assert "signal_runs" not in remaining
    assert pre_0003_snapshot(conn) == before, "reversing 0003 must not touch pre-0003 rows"
    assert [m.version for m in migration_history(conn)] == [1, 2]
    assert "schema_migrations" in remaining


def test_reapply_after_revert_is_deterministic(tmp_path, project_root):
    conn = connect(tmp_path / "reapply.sqlite3")
    apply_migrations(conn, legacy_dir(tmp_path, project_root))
    seed_pre_0003(conn)
    before = pre_0003_snapshot(conn)

    apply_migrations(conn, project_root / "migrations")
    revert_migration(conn, project_root / "migrations", 3)

    assert apply_migrations(conn, project_root / "migrations") == [3]
    assert {"signals", "signal_runs"} <= table_names(conn)
    assert pre_0003_snapshot(conn) == before
    assert [m.version for m in migration_history(conn)] == [1, 2, 3]
    # a second apply is a no-op, not a re-run
    assert apply_migrations(conn, project_root / "migrations") == []


def test_revert_refuses_an_unapplied_version(tmp_path, project_root):
    conn = connect(tmp_path / "unapplied.sqlite3")
    apply_migrations(conn, legacy_dir(tmp_path, project_root))

    with pytest.raises(MigrationError, match="is not applied"):
        revert_migration(conn, project_root / "migrations", 3)


def test_revert_refuses_out_of_order(tmp_path, project_root):
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)
    (migrations / "0004_probe.sql").write_text("CREATE TABLE probe (id INTEGER PRIMARY KEY);\n", encoding="utf-8")
    (migrations / "rollback" / "0004_probe.down.sql").write_text("DROP TABLE probe;\n", encoding="utf-8")

    conn = connect(tmp_path / "ordering.sqlite3")
    assert apply_migrations(conn, migrations) == [1, 2, 3, 4]

    with pytest.raises(MigrationError, match="later migrations"):
        revert_migration(conn, migrations, 3)
    assert {"signals", "signal_runs", "probe"} <= table_names(conn)


def test_revert_requires_exactly_one_down_file(tmp_path, project_root):
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)
    shutil.rmtree(migrations / "rollback")

    conn = connect(tmp_path / "nodown.sqlite3")
    apply_migrations(conn, migrations)

    with pytest.raises(MigrationError, match="exactly one down migration"):
        revert_migration(conn, migrations, 3)
    assert "signals" in table_names(conn)


def test_revert_refuses_a_forward_file_that_changed(tmp_path, project_root):
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)
    conn = connect(tmp_path / "tampered.sqlite3")
    apply_migrations(conn, migrations)

    target = migrations / "0003_signals.sql"
    target.write_text(target.read_text(encoding="utf-8") + "\n-- edited after apply\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="changed after being applied"):
        revert_migration(conn, migrations, 3)
    assert "signals" in table_names(conn)


def test_revert_is_atomic_when_a_table_is_missing(tmp_path, project_root):
    """Negative control for the atomicity defect: a failed DROP must undo the rest.

    ``signals`` is dropped first inside the transaction; if ``signal_runs`` then
    fails, the rollback must bring ``signals`` back and leave the 0003 row in the
    ledger. A non-transactional implementation would leave the schema half gone
    while still claiming 0003 is applied.
    """
    conn = connect(tmp_path / "atomic.sqlite3")
    apply_migrations(conn, project_root / "migrations")

    conn.execute("DROP TABLE signal_runs")
    conn.commit()

    with pytest.raises(sqlite3.OperationalError):
        revert_migration(conn, project_root / "migrations", 3)

    assert "signals" in table_names(conn), "the first DROP must have been rolled back"
    assert [m.version for m in migration_history(conn)] == [1, 2, 3]


def test_down_file_is_never_discovered_as_a_forward_migration(tmp_path, project_root):
    forward = [p.name for p in discover_migrations(project_root / "migrations")]
    assert forward == ["0001_init.sql", "0002_market_data.sql", "0003_signals.sql"]
    assert all(".down." not in name for name in forward)

    down = [p.name for p in discover_down_migrations(project_root / "migrations" / "rollback")]
    assert down == ["0003_signals.down.sql"]

    conn = connect(tmp_path / "discovery.sqlite3")
    assert apply_migrations(conn, project_root / "migrations") == [1, 2, 3]


# --------------------------------------------------------------------------- #
# S6 hardening: the reverse may not reach anything the forward did not create
# --------------------------------------------------------------------------- #


def test_down_script_may_only_drop_objects_the_forward_created(tmp_path, project_root):
    """Mutation control: a reverse that reaches a pre-0003 table must be refused.

    Without the whitelist this script would drop ``bars`` — real pre-0003 data —
    and still delete the ``schema_migrations`` row, recording a reversal that
    destroyed history.
    """
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)
    (migrations / "rollback" / "0003_signals.down.sql").write_text(
        "DROP TABLE signals;\nDROP TABLE signal_runs;\nDROP TABLE bars;\n", encoding="utf-8"
    )

    conn = connect(tmp_path / "foreign.sqlite3")
    assert apply_migrations(conn, legacy_dir(tmp_path, project_root)) == [1, 2]
    seed_pre_0003(conn)
    assert apply_migrations(conn, migrations) == [3]

    with pytest.raises(MigrationError, match="did not create"):
        revert_migration(conn, migrations, 3)

    assert {"signals", "signal_runs", "bars", "feed_runs"} <= table_names(conn)
    assert pre_0003_snapshot(conn) == (1, 1, 1.5)
    assert [m.version for m in migration_history(conn)] == [1, 2, 3]


def test_down_script_rejects_anything_that_is_not_a_plain_drop(tmp_path, project_root):
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)

    conn = connect(tmp_path / "nonstd.sqlite3")
    apply_migrations(conn, migrations)
    seed_pre_0003(conn)

    (migrations / "rollback" / "0003_signals.down.sql").write_text("DELETE FROM bars;\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="not a plain DROP"):
        revert_migration(conn, migrations, 3)

    (migrations / "rollback" / "0003_signals.down.sql").write_text(
        "-- harmless looking\nDROP TABLE signals;\nALTER TABLE bars ADD COLUMN note TEXT;\n",
        encoding="utf-8",
    )
    with pytest.raises(MigrationError, match="not a plain DROP"):
        revert_migration(conn, migrations, 3)

    assert pre_0003_snapshot(conn) == (1, 1, 1.5)
    assert "signals" in table_names(conn)


def test_revert_refuses_a_drifted_table(tmp_path, project_root):
    """If the live table is not the one 0003 declares, dropping it would lose data."""
    conn = prepared_db(tmp_path, project_root, "drift.sqlite3")
    conn.execute("ALTER TABLE signals ADD COLUMN note TEXT")
    conn.commit()

    with pytest.raises(MigrationError, match="drifted"):
        revert_migration(conn, project_root / "migrations", 3)

    assert {"signals", "signal_runs"} <= table_names(conn)
    assert [m.version for m in migration_history(conn)] == [1, 2, 3]


def test_incomplete_down_script_is_refused_and_rolled_back(tmp_path, project_root):
    """Post-condition control: dropping only half of 0003 must leave no trace."""
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)
    conn = prepared_db(tmp_path, project_root, "partial.sqlite3")
    before = pre_0003_snapshot(conn)

    (migrations / "rollback" / "0003_signals.down.sql").write_text("DROP TABLE signals;\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="left objects behind"):
        revert_migration(conn, migrations, 3)

    assert {"signals", "signal_runs"} <= table_names(conn), "the partial reversal must be rolled back"
    assert pre_0003_snapshot(conn) == before
    assert [m.version for m in migration_history(conn)] == [1, 2, 3]


def test_reversal_plan_is_reviewable_before_acting(tmp_path, project_root):
    conn = prepared_db(tmp_path, project_root, "plan.sqlite3")

    plan = reversal_plan(conn, project_root / "migrations", 3)

    assert plan.version == 3
    assert plan.forward_filename == "0003_signals.sql"
    assert plan.down_filename == "0003_signals.down.sql"
    assert plan.tables == ("signal_runs", "signals")
    assert plan.indexes == ("idx_signal_runs_window", "idx_signals_run")
    assert len(plan.statements) == 2

    down_text = (project_root / "migrations" / "rollback" / "0003_signals.down.sql").read_text(encoding="utf-8")
    assert plan.down_sha256 == "sha256:" + hashlib.sha256(down_text.encode("utf-8")).hexdigest()
    assert {"signals", "signal_runs"} <= table_names(conn), "a plan must not change the schema"


def test_forward_file_copied_into_rollback_is_not_a_candidate(tmp_path, project_root):
    """Only ``NNNN_name.down.sql`` counts; a stray forward copy leaves one candidate."""
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)
    shutil.copy(migrations / "0003_signals.sql", migrations / "rollback" / "0003_signals.sql")

    names = [p.name for p in discover_down_migrations(migrations / "rollback")]
    assert names == ["0003_signals.down.sql"]

    conn = prepared_db(tmp_path, project_root, "stray.sqlite3")
    assert revert_migration(conn, migrations, 3) == 3
    assert "signals" not in table_names(conn)


def test_revert_removes_the_0003_indexes(tmp_path, project_root):
    conn = prepared_db(tmp_path, project_root, "indexes.sqlite3")
    assert OWNED_INDEXES <= index_names(conn)

    revert_migration(conn, project_root / "migrations", 3)

    assert not (OWNED_INDEXES & index_names(conn))


# --------------------------------------------------------------------------- #
# S7 finding F1: adoption of a pre-existing table must be refused at apply time
# --------------------------------------------------------------------------- #


def test_apply_refuses_to_adopt_a_preexisting_table(tmp_path, project_root):
    """F1 regression: a same-named pre-0003 table must never be adopted, so it can never be dropped.

    The pre-existing table has the same nine column names as 0003 declares but
    different types and no primary key — the shape a pre-S5 prototype would have.
    Before the fix, apply recorded 0003 anyway and the reverse deleted the rows.
    """
    conn = connect(tmp_path / "adopt.sqlite3")
    assert apply_migrations(conn, legacy_dir(tmp_path, project_root)) == [1, 2]
    conn.execute(
        "CREATE TABLE signals (symbol TEXT, timeframe TEXT, bar_time_utc TEXT, strategy_id TEXT, "
        "direction TEXT, strength REAL, reason_code TEXT, run_id INTEGER, created_utc TEXT)"
    )
    conn.execute(
        "INSERT INTO signals (symbol, timeframe, bar_time_utc, strategy_id, direction, strength, "
        "reason_code, run_id, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
        ("XAUUSD.", "M5", START.isoformat(), "legacy", "LONG", 0.5, "LEGACY", 7, START.isoformat()),
    )
    conn.commit()

    with pytest.raises(MigrationError, match="would adopt"):
        apply_migrations(conn, project_root / "migrations")

    assert [m.version for m in migration_history(conn)] == [1, 2], "an adoption must not be recorded"
    assert conn.execute("SELECT COUNT(*) AS c FROM signals").fetchone()["c"] == 1
    assert "signal_runs" not in table_names(conn)

    with pytest.raises(MigrationError, match="is not applied"):
        revert_migration(conn, project_root / "migrations", 3)
    assert conn.execute("SELECT COUNT(*) AS c FROM signals").fetchone()["c"] == 1


def test_revert_refuses_a_table_replaced_after_apply(tmp_path, project_root):
    """Type-only drift: same column names, different declared type, must be refused."""
    conn = prepared_db(tmp_path, project_root, "replaced.sqlite3")
    conn.execute("DROP TABLE signals")
    conn.execute(
        "CREATE TABLE signals (symbol TEXT, timeframe TEXT, bar_time_utc TEXT, strategy_id TEXT, "
        "direction TEXT, strength REAL, reason_code TEXT, run_id INTEGER, created_utc TEXT)"
    )
    conn.commit()

    with pytest.raises(MigrationError, match="drifted"):
        revert_migration(conn, project_root / "migrations", 3)

    assert "signals" in table_names(conn)
    assert [m.version for m in migration_history(conn)] == [1, 2, 3]


def test_comment_in_forward_cannot_widen_the_reverse_whitelist(tmp_path, project_root):
    """A ``--`` comment must not turn a real table into a legal DROP target."""
    migrations = tmp_path / "mig"
    shutil.copytree(project_root / "migrations", migrations)
    (migrations / "0004_probe.sql").write_text(
        "-- a comment is not a drop licence: CREATE TABLE bars\n"
        "CREATE TABLE probe (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )
    (migrations / "rollback" / "0004_probe.down.sql").write_text(
        "DROP TABLE probe;\nDROP TABLE bars;\n", encoding="utf-8"
    )

    conn = connect(tmp_path / "comment.sqlite3")
    assert apply_migrations(conn, migrations) == [1, 2, 3, 4]
    seed_pre_0003(conn)

    with pytest.raises(MigrationError, match="did not create"):
        revert_migration(conn, migrations, 4)

    assert "bars" in table_names(conn)
    assert pre_0003_snapshot(conn) == (1, 1, 1.5)
    assert [m.version for m in migration_history(conn)] == [1, 2, 3, 4]
