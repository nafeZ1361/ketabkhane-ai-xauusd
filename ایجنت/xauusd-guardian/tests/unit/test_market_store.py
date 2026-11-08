"""Persistence: idempotency, revisions, dedupe, quota, run lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from guardian.contracts.market import FeedRun, MarketBar, MarketTick, Timeframe
from guardian.storage.db import apply_migrations, connect
from guardian.storage.market_store import MarketStore, QuotaExceeded

START = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)


@pytest.fixture()
def store(tmp_path, project_root):
    conn = connect(tmp_path / "market.sqlite3")
    applied = apply_migrations(conn, project_root / "migrations")
    assert applied == [1, 2, 3], applied
    return MarketStore(conn, quota_bytes=50_000_000), conn


def bar(i=0, close=None, tf=Timeframe.M1):
    return MarketBar(
        symbol="XAUUSD.",
        timeframe=tf,
        time_utc=START + timedelta(minutes=i),
        open=4000.0,
        high=4001.0,
        low=3999.0,
        close=close if close is not None else 4000.0,
        tick_volume=5,
    )


def tick(ms=1_800_000_000_000, bid=4000.0, ask=4000.2):
    return MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=ms, bid=bid, ask=ask)


def test_bars_are_idempotent(store):
    s, conn = store
    first = s.upsert_bars("run-1", [bar(0), bar(1)])
    assert (first.inserted, first.revised) == (2, 0)

    again = s.upsert_bars("run-2", [bar(0), bar(1)])
    assert (again.inserted, again.revised, again.unchanged) == (0, 0, 2)
    assert conn.execute("SELECT COUNT(*) FROM bars").fetchone()[0] == 2


def test_revised_bar_keeps_the_old_version(store):
    s, conn = store
    s.upsert_bars("run-1", [bar(0, close=4000.0)])
    result = s.upsert_bars("run-2", [bar(0, close=4050.0)])

    assert result.revised == 1
    assert conn.execute("SELECT COUNT(*) FROM bar_revisions").fetchone()[0] == 2
    current = conn.execute("SELECT close FROM bars").fetchone()[0]
    assert current == 4050.0


def test_ticks_dedupe_on_the_stated_key(store):
    s, conn = store
    inserted = s.insert_ticks("run-1", [tick(), tick(), tick(ask=4000.4)])
    assert inserted == 2
    assert conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0] == 2


def test_quota_is_enforced_per_chunk(store):
    s, _ = store
    s._quota = 1_000  # type: ignore[attr-defined]
    with pytest.raises(QuotaExceeded, match="quota"):
        s.insert_ticks("run-1", [tick(ms=1_800_000_000_000 + i) for i in range(100)])


def test_run_lifecycle_and_health(store):
    s, conn = store
    run = FeedRun(run_id="r1", symbol="XAUUSD.", kind="bars", timeframe=Timeframe.M1, started_utc=START)
    s.record_run_start(run)
    s.finish_run("r1", status="OK", inserted=2, gaps=0)

    row = conn.execute("SELECT status, inserted, finished_utc FROM feed_runs WHERE run_id='r1'").fetchone()
    assert row["status"] == "OK"
    assert row["inserted"] == 2
    assert row["finished_utc"] is not None

    health = s.health()
    assert health["bars"] == 0 and health["runs"] == 1


def test_gaps_and_quarantine_are_recorded(store):
    s, conn = store
    s.record_gaps("r1", "XAUUSD.", "M1", [(START, 3)])
    s.quarantine("r1", "XAUUSD.", "H1", "DAILY_RESOLUTION_DETECTED")

    assert conn.execute("SELECT SUM(bars_missing) FROM data_gaps").fetchone()[0] == 3
    assert conn.execute("SELECT reason FROM quarantined_series").fetchone()[0] == "DAILY_RESOLUTION_DETECTED"


def test_last_bar_is_returned(store):
    s, _ = store
    s.upsert_bars("r1", [bar(0), bar(5)])
    last = s.last_bar("XAUUSD.", "M1")
    assert last is not None
    assert last["time_utc"].startswith("2026-11-04T14:05")
