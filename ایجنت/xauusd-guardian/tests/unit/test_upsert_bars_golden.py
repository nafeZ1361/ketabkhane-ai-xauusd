"""Golden behaviour of MarketStore.upsert_bars: counts, digests, revisions.

Written before the Stage-3 rewrite so the batch implementation must reproduce the
per-row implementation exactly.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from guardian.contracts.market import MarketBar, Timeframe
from guardian.storage.db import apply_migrations, connect
from guardian.storage.market_store import MarketStore

MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_bars(n: int) -> list[MarketBar]:
    return [
        MarketBar("XAUUSD.", Timeframe.M5, START + timedelta(minutes=5 * i),
                  1.0 + i, 2.0 + i, 0.5 + i, 1.5 + i, 10, 5, 0.0)
        for i in range(n)
    ]


def make_store(tmp_path) -> MarketStore:
    conn = connect(tmp_path / "golden.sqlite3")
    apply_migrations(conn, MIGRATIONS)
    return MarketStore(conn, quota_bytes=10**9)


def test_insert_then_idempotent(tmp_path):
    store = make_store(tmp_path)
    bars = make_bars(50)

    first = store.upsert_bars("run-1", bars)
    assert (first.inserted, first.revised, first.unchanged) == (50, 0, 0)

    second = store.upsert_bars("run-1", bars)
    assert (second.inserted, second.revised, second.unchanged) == (0, 0, 50)

    rows = store._conn.execute(
        "SELECT time_utc, content_sha256 FROM bars ORDER BY time_utc"
    ).fetchall()
    assert len(rows) == 50
    assert [r["content_sha256"] for r in rows] == [b.content_sha256 for b in bars]
    assert store._conn.execute("SELECT COUNT(*) FROM bar_revisions").fetchone()[0] == 50


def test_revision_is_recorded_once(tmp_path):
    store = make_store(tmp_path)
    bars = make_bars(5)
    store.upsert_bars("run-1", bars)

    changed = [
        MarketBar(b.symbol, b.timeframe, b.time_utc, b.open, b.high, b.low,
                  b.close + 10.0, b.tick_volume, b.spread_points, b.real_volume)
        for b in bars
    ]
    result = store.upsert_bars("run-2", changed)
    assert (result.inserted, result.revised, result.unchanged) == (0, 5, 0)

    rows = store._conn.execute(
        "SELECT close, content_sha256 FROM bars ORDER BY time_utc"
    ).fetchall()
    assert [r["content_sha256"] for r in rows] == [b.content_sha256 for b in changed]
    assert store._conn.execute("SELECT COUNT(*) FROM bar_revisions").fetchone()[0] == 10
