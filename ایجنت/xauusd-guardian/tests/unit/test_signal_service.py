"""S5: signal service — determinism, closed candles, quarantine, fail-closed writes."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal

import pytest

from guardian.application.signal_service import SignalService
from guardian.contracts.market import FeedRun, MarketBar, Timeframe
from guardian.contracts.signals import SignalError, StrategySpec
from guardian.domain.strategy import ema_cross
from guardian.storage.db import apply_migrations, connect
from guardian.storage.market_store import MarketStore

SYMBOL = "XAUUSD."
TF = Timeframe.M5
START = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
#: 120 M5 bars; bar i closes at START + (i+1)*5min, so the last closes at +600min.
NOW = START + timedelta(minutes=600)
QUOTA = 50_000_000

FULL = [100.0 + i for i in range(60)] + [160.0 - 3.0 * (i - 60) for i in range(60, 120)]


class _NoOffsetTZ(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


class _BadTypeTZ(tzinfo):
    def utcoffset(self, dt):
        return "not-a-timedelta"

    def dst(self, dt):
        return None


def bars_from(first_index: int, count: int) -> list[MarketBar]:
    return [
        MarketBar(
            symbol=SYMBOL,
            timeframe=TF,
            time_utc=START + timedelta(minutes=5 * (first_index + i)),
            open=FULL[first_index + i],
            high=FULL[first_index + i] + 1,
            low=FULL[first_index + i] - 1,
            close=FULL[first_index + i],
            tick_volume=1,
        )
        for i in range(count)
    ]


def make_bars(n: int = 120) -> list[MarketBar]:
    return bars_from(0, n)


def new_conn(tmp_path, project_root, name="signals.sqlite3"):
    conn = connect(tmp_path / name)
    apply_migrations(conn, project_root / "migrations")
    return conn


def seed(conn, *, run_id="run-1", bars=None, status="OK"):
    store = MarketStore(conn, quota_bytes=QUOTA)
    store.record_run_start(
        FeedRun(run_id=run_id, symbol=SYMBOL, kind="bars", timeframe=TF, started_utc=START, status=status)
    )
    store.upsert_bars(run_id, bars if bars is not None else make_bars())
    return store


@pytest.fixture()
def conn(tmp_path, project_root):
    return new_conn(tmp_path, project_root)


# -- persistence ------------------------------------------------------------
def test_persists_run_and_signals(conn):
    seed(conn)
    outcome = SignalService(conn).run(now=NOW)

    assert outcome.created is True
    assert outcome.run.bars_seen == 120
    assert outcome.signals, "the synthetic reversal must produce a cross"
    assert outcome.written == len(outcome.signals)

    row = conn.execute("SELECT * FROM signal_runs WHERE run_id = ?", (outcome.run.run_id,)).fetchone()
    assert row["symbol"] == SYMBOL
    assert row["strategy_id"] == "ema_cross_v1"
    assert row["timeframe"] == "M5"
    assert row["bars_seen"] == 120
    assert row["signals"] == len(outcome.signals)
    assert row["status"] == "OK"
    assert conn.execute("SELECT COUNT(*) AS c FROM signals").fetchone()["c"] == len(outcome.signals)


def test_strength_round_trips_as_exact_decimal(conn):
    seed(conn)
    outcome = SignalService(conn).run(now=NOW)

    stored = conn.execute("SELECT strength FROM signals ORDER BY bar_time_utc LIMIT 1").fetchone()["strength"]
    assert isinstance(stored, str)
    assert Decimal(stored) == outcome.signals[0].strength
    assert Decimal(stored).is_finite()
    assert Decimal(0) <= Decimal(stored) <= Decimal(1)


def test_strategy_and_timeframe_are_enforced(conn):
    seed(conn)

    with pytest.raises(SignalError):
        SignalService(conn, timeframe=Timeframe.H1)

    other = StrategySpec(id="ema_cross_v2", version="1", params={}, warmup_bars=50)
    with pytest.raises(SignalError):
        SignalService(conn, spec=other)


# -- closed candles / look-ahead -------------------------------------------
def test_forming_bar_is_excluded_not_trimmed(conn):
    """A stored forming bar must be skipped; evaluate() would refuse it outright."""
    forming = MarketBar(
        symbol=SYMBOL, timeframe=TF, time_utc=START + timedelta(minutes=600),
        open=1.0, high=2.0, low=0.5, close=1.5, tick_volume=1,
    )
    seed(conn, bars=make_bars() + [forming])

    with pytest.raises(SignalError, match="forming"):
        ema_cross.evaluate(make_bars() + [forming], now=NOW)

    outcome = SignalService(conn).run(now=NOW)
    assert outcome.run.bars_seen == 120
    assert all(s.bar_time_utc < START + timedelta(minutes=600) for s in outcome.signals)


def test_no_look_ahead_property(conn, tmp_path, project_root):
    seed(conn)
    full = SignalService(conn).run(now=NOW).signals
    assert full

    cut = 90
    other = new_conn(tmp_path, project_root, "cut.sqlite3")
    seed(other, bars=make_bars()[:cut])
    partial = SignalService(other).run(now=START + timedelta(minutes=5 * cut)).signals

    last_allowed = START + timedelta(minutes=5 * (cut - 1))
    assert list(partial) == [s for s in full if s.bar_time_utc <= last_allowed]


# -- quarantine -------------------------------------------------------------
def test_quarantined_run_cannot_reach_the_strategy(conn):
    store = seed(conn)
    assert SignalService(conn).run(now=NOW).run.bars_seen == 120

    store.quarantine_run("run-1", "synthetic test quarantine")

    with pytest.raises(SignalError, match="no closed bars"):
        SignalService(conn).run(now=NOW)


def test_quarantine_only_removes_its_own_run(conn):
    seed(conn, run_id="run-a", bars=bars_from(0, 60))
    seed(conn, run_id="run-b", bars=bars_from(60, 60))

    assert SignalService(conn).run(now=NOW).run.bars_seen == 120

    MarketStore(conn, quota_bytes=QUOTA).quarantine_run("run-b", "synthetic test quarantine")

    remaining = SignalService(conn).run(now=NOW)
    assert remaining.run.bars_seen == 60
    assert remaining.run.signals == 0  # the rising half alone has no cross


# -- fail closed ------------------------------------------------------------
@pytest.mark.parametrize(
    "moment",
    [
        datetime(2026, 11, 5, 20, 0),                       # naive
        datetime(2026, 11, 5, 20, 0, tzinfo=_NoOffsetTZ()),  # utcoffset() -> None
        datetime(2026, 11, 5, 20, 0, tzinfo=_BadTypeTZ()),   # utcoffset() -> str
    ],
)
def test_unusable_now_is_rejected(conn, moment):
    seed(conn)
    with pytest.raises(SignalError, match="timezone-aware|valid UTC offset"):
        SignalService(conn).run(now=moment)


def test_empty_database_fails_closed(conn):
    with pytest.raises(SignalError, match="no closed bars"):
        SignalService(conn).run(now=NOW)


def test_insufficient_bars_fail_closed(conn):
    seed(conn, bars=make_bars(40))
    with pytest.raises(SignalError, match="insufficient"):
        SignalService(conn).run(now=NOW)


def test_naive_stored_bar_time_fails_closed(conn):
    conn.execute(
        "INSERT INTO feed_runs (run_id, symbol, kind, started_utc, status) VALUES (?,?,?,?,?)",
        ("run-naive", SYMBOL, "bars", START.isoformat(), "OK"),
    )
    conn.execute(
        "INSERT INTO bars (symbol, timeframe, time_utc, open, high, low, close, tick_volume, "
        "spread_points, real_volume, content_sha256, first_seen_utc, last_seen_utc, run_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (SYMBOL, "M5", "2026-11-05T08:00:00", 1.0, 2.0, 0.5, 1.5, 1, 0, 0.0, "sha", "x", "y", "run-naive"),
    )
    conn.commit()

    with pytest.raises(SignalError, match="not timezone-aware"):
        SignalService(conn).run(now=NOW)


# -- determinism ------------------------------------------------------------
def test_repeat_run_is_idempotent(conn):
    seed(conn)
    service = SignalService(conn)
    first = service.run(now=NOW)
    second = service.run(now=NOW)

    assert second.run.run_id == first.run.run_id
    assert second.created is False
    assert second.written == 0
    assert second.identical == len(first.signals)
    assert conn.execute("SELECT COUNT(*) AS c FROM signals").fetchone()["c"] == len(first.signals)
    assert conn.execute("SELECT COUNT(*) AS c FROM signal_runs").fetchone()["c"] == 1


def test_run_id_does_not_depend_on_now(conn):
    seed(conn)
    early = SignalService(conn).run(now=NOW)
    late = SignalService(conn).run(now=NOW + timedelta(hours=5))

    assert early.bars_digest == late.bars_digest
    assert early.run.run_id == late.run.run_id


def test_timezone_equivalent_now_is_the_same_instant(conn):
    seed(conn)
    utc = SignalService(conn).run(now=NOW)
    shifted = SignalService(conn).run(now=NOW.astimezone(timezone(timedelta(hours=3, minutes=30))))

    assert shifted.run.run_id == utc.run.run_id
    assert shifted.written == 0
    assert shifted.identical == len(utc.signals)


# -- conflict handling ------------------------------------------------------
def test_conflicting_stored_signal_fails_closed(conn):
    seed(conn)
    service = SignalService(conn)
    outcome = service.run(now=NOW)
    target = outcome.signals[0]
    flipped = "SHORT" if target.direction.value == "LONG" else "LONG"
    conn.execute(
        "UPDATE signals SET direction = ? WHERE bar_time_utc = ?",
        (flipped, target.bar_time_utc.isoformat()),
    )
    conn.commit()

    with pytest.raises(SignalError, match="conflicts"):
        service.run(now=NOW)

    after = conn.execute(
        "SELECT direction FROM signals WHERE bar_time_utc = ?", (target.bar_time_utc.isoformat(),)
    ).fetchone()["direction"]
    assert after == flipped, "the stored row must be left untouched"


def test_failure_rolls_back_the_run_row(conn):
    """A run row written before the conflict must not survive the rollback."""
    seed(conn)
    service = SignalService(conn)
    first = service.run(now=NOW)
    target = first.signals[0]
    flipped = "SHORT" if target.direction.value == "LONG" else "LONG"

    conn.execute("DELETE FROM signal_runs")
    conn.execute(
        "UPDATE signals SET direction = ? WHERE bar_time_utc = ?",
        (flipped, target.bar_time_utc.isoformat()),
    )
    conn.commit()

    with pytest.raises(SignalError, match="conflicts"):
        service.run(now=NOW)

    assert conn.execute("SELECT COUNT(*) AS c FROM signal_runs").fetchone()["c"] == 0


# -- boundary ---------------------------------------------------------------
def test_new_s5_modules_introduce_no_trading_surface(project_root):
    banned_modules = {"MetaTrader5", "mt5"}
    banned_calls = {"order_send", "order_check", "positions_get", "account_info", "symbol_info_tick"}
    targets = [
        project_root / "src" / "guardian" / "application" / "signal_service.py",
        project_root / "scripts" / "signals.py",
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert "MetaTrader5" not in text
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in banned_modules, (path, alias.name)
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in banned_modules, path
            elif isinstance(node, ast.Call):
                called = getattr(node.func, "attr", getattr(node.func, "id", ""))
                assert called not in banned_calls, (path, called)
