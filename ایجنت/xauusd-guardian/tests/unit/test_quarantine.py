"""Run quarantine: hidden from readers, reversible, never destructive."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from guardian.contracts.market import FeedRun, MarketBar, MarketTick, Timeframe
from guardian.storage.db import apply_migrations, connect
from guardian.storage.market_store import MarketStore

START = datetime(2026, 11, 5, 10, 31, 53, tzinfo=timezone.utc)


@pytest.fixture()
def store(tmp_path, project_root):
    conn = connect(tmp_path / "market.sqlite3")
    apply_migrations(conn, project_root / "migrations")
    return MarketStore(conn, quota_bytes=50_000_000), conn


def seed(s: MarketStore, run_id: str = "run-tick", status: str = "OK") -> None:
    run = FeedRun(run_id=run_id, symbol="XAUUSD.", kind="ticks", started_utc=START)
    s.record_run_start(run)
    s.insert_ticks(run_id, [
        MarketTick(symbol="XAUUSD.", time_utc=START + timedelta(milliseconds=i),
                   time_msc=1_800_000_000_000 + i, bid=4000.0 + i, ask=4000.2 + i)
        for i in range(5)
    ])
    s.finish_run(run_id, status=status, inserted=5)


def row_count(conn, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_quarantine_hides_ticks_and_restore_returns_them(store):
    s, conn = store
    seed(s)
    assert s.health()["ticks"] == 5

    previous = s.quarantine_run("run-tick", "request window built before A2")
    assert previous == "OK"
    assert s.health()["ticks"] == 0, "a quarantined run must not reach readers"
    assert s.health()["quarantined_runs"] == 1
    assert s.quarantined_runs() == ["run-tick"]

    s.restore_run("run-tick")
    assert s.health()["ticks"] == 5
    assert s.health()["quarantined_runs"] == 0
    assert s.quarantined_runs() == []


def test_quarantine_keeps_every_row_and_the_audit_trail(store):
    s, conn = store
    seed(s)
    s.quarantine_run("run-tick", "investigation")
    assert row_count(conn, "ticks") == 5
    event = conn.execute(
        "SELECT event_type, message, payload FROM audit_events WHERE run_id = 'run-tick' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert event["event_type"] == "QUARANTINE_APPLIED"
    assert event["message"] == "investigation"
    assert '"previous_status": "OK"' in event["payload"]
    assert conn.execute("SELECT status FROM feed_runs WHERE run_id='run-tick'").fetchone()[0] == "QUARANTINED"

    s.restore_run("run-tick")
    assert row_count(conn, "ticks") == 5
    assert conn.execute("SELECT status FROM feed_runs WHERE run_id='run-tick'").fetchone()[0] == "OK"
    lifted = conn.execute(
        "SELECT COUNT(*) FROM audit_events WHERE run_id='run-tick' AND event_type='QUARANTINE_LIFTED'"
    ).fetchone()[0]
    assert lifted == 1


def test_restore_is_exact_for_a_degraded_run(store):
    s, _ = store
    seed(s, status="DEGRADED")
    s.quarantine_run("run-tick", "check")
    s.restore_run("run-tick")
    assert s._conn.execute("SELECT status FROM feed_runs WHERE run_id='run-tick'").fetchone()[0] == "DEGRADED"


def test_quarantine_is_idempotent(store):
    s, _ = store
    seed(s)
    s.quarantine_run("run-tick", "first")
    s.quarantine_run("run-tick", "second")
    assert s.quarantined_runs() == ["run-tick"]
    assert row_count(s._conn, "audit_events") == 1


def test_unknown_run_is_refused(store):
    s, _ = store
    with pytest.raises(ValueError, match="unknown run"):
        s.quarantine_run("nope", "reason")
    with pytest.raises(ValueError, match="unknown run"):
        s.restore_run("nope")


def test_last_bar_skips_a_quarantined_run(store):
    s, conn = store
    run = FeedRun(run_id="run-bars", symbol="XAUUSD.", kind="bars", timeframe=Timeframe.M1, started_utc=START)
    s.record_run_start(run)
    s.upsert_bars("run-bars", [
        MarketBar(symbol="XAUUSD.", timeframe=Timeframe.M1, time_utc=START, open=4000.0,
                  high=4001.0, low=3999.0, close=4000.5, tick_volume=5)
    ])
    s.finish_run("run-bars", status="OK", inserted=1)
    assert s.last_bar("XAUUSD.", "M1") is not None
    assert s.health()["bars"] == 1

    s.quarantine_run("run-bars", "suspect")
    assert s.last_bar("XAUUSD.", "M1") is None, "a quarantined bar must not be served"
    assert s.health()["bars"] == 0

    s.restore_run("run-bars")
    assert s.last_bar("XAUUSD.", "M1") is not None
    assert s.health()["bars"] == 1
    assert row_count(conn, "bars") == 1


def test_cli_apply_status_restore(tmp_path, project_root, monkeypatch, capsys):
    import sys

    sys.path.insert(0, str(project_root / "scripts"))
    import quarantine  # noqa: PLC0415

    db = tmp_path / "cli.sqlite3"
    conn = connect(db)
    apply_migrations(conn, project_root / "migrations")
    seed(MarketStore(conn, quota_bytes=50_000_000), run_id="cli-run")
    conn.close()

    assert quarantine.main(["apply", "--run-id", "cli-run", "--reason", "cli test", "--db", str(db)]) == 0
    applied = capsys.readouterr().out
    assert '"status": "QUARANTINED"' in applied and '"previous_status": "OK"' in applied

    assert quarantine.main(["status", "--db", str(db)]) == 0
    status_out = capsys.readouterr().out
    assert '"quarantined_runs": [' in status_out and "cli-run" in status_out
    assert '"ticks": 0' in status_out

    assert quarantine.main(["restore", "--run-id", "cli-run", "--db", str(db)]) == 0
    restored = capsys.readouterr().out
    assert '"status": "OK"' in restored
    assert quarantine.main(["apply", "--db", str(db)]) == 2
