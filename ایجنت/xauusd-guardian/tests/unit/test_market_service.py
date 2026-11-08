"""Collection orchestration: identity gate, failure modes, per-timeframe runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from guardian.application.market_data_service import MarketDataService, MarketRunConfig
from guardian.contracts.market import MarketBar, MarketTick, Timeframe
from guardian.contracts.schemas import SymbolSpec
from guardian.domain.market.broker_clock import BrokerClock
from guardian.domain.market.session import SessionCalendar
from guardian.storage.db import apply_migrations, connect
from guardian.storage.market_store import MarketStore

START = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)
NOW = START + timedelta(hours=1, minutes=1)

GOOD_SPEC = SymbolSpec(
    name="XAUUSD.",
    path=r"Pure\Spot Metals\Gold\XAUUSD.",
    description="Gold vs US Dollar / Spot",
    trade_mode=4,
    digits=2,
    point=0.01,
    tick_size=0.01,
    contract_size=100.0,
    currency_base="USD",
    currency_profit="USD",
    visible=True,
)

DEMO = {"trade_mode": "DEMO", "server": "AronMarkets-Demo", "company": "Aron Markets Ltd",
        "currency": "USD", "leverage": "400"}


def series(n=60, tf=Timeframe.M1, start=START):
    step = tf.minutes
    out = []
    for i in range(n):
        out.append(
            MarketBar(
                symbol="XAUUSD.",
                timeframe=tf,
                time_utc=start + timedelta(minutes=step * i),
                open=4000.0, high=4001.0, low=3999.0, close=4000.5,
                tick_volume=5, spread_points=20,
            )
        )
    return out


class FakeMarketAdapter:
    def __init__(self, *, bars=None, ticks=None, identity=None, specs=None, rates_none=False,
                 offset=7200, mad_s=0):
        self._bars = bars or {}
        self._ticks = ticks
        self._identity = identity or dict(DEMO)
        self._specs = specs if specs is not None else [GOOD_SPEC]
        self._rates_none = rates_none
        self._offset = offset
        self._mad = mad_s
        self.broker_clock = BrokerClock()
        self.attach_calls = 0
        self.detached = False

    def estimate_server_offset(self, symbol, samples=10, pause_s=0.0):
        if self._offset is None:
            return None
        return (self._offset, self._mad, 10)

    def attach(self):
        self.attach_calls += 1
        return {"terminal_path": r"C:\Program Files\Aron Markets MT5", "build": 6230}

    def detach(self):
        self.detached = True

    def account_identity(self):
        return dict(self._identity)

    def symbol_specs(self):
        return list(self._specs)

    def rates(self, symbol, timeframe, count):
        if self._rates_none:
            return None
        return list(self._bars.get(timeframe, []))

    def ticks(self, symbol, start_utc, limit, end_utc=None):
        return self._ticks


@pytest.fixture()
def store(tmp_path, project_root):
    conn = connect(tmp_path / "market.sqlite3")
    apply_migrations(conn, project_root / "migrations")
    return MarketStore(conn, quota_bytes=50_000_000)


def service(adapter, store, **cfg):
    return MarketDataService(
        adapter, store, SessionCalendar(), MarketRunConfig(**cfg), clock=lambda: NOW
    )


def test_measured_offset_is_recorded_as_evidence_not_as_a_conversion_input(store):
    """A6: the measurement reaches the time_sync table; conversion stays model-driven."""
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series()}, offset=7200)
    service(adapter, store).collect_bars([Timeframe.M1], 60)
    row = store._conn.execute("SELECT status, offset_ms, samples FROM time_sync").fetchone()
    assert row["status"] == "HIGH"
    assert row["offset_ms"] == 7_200_000.0
    assert row["samples"] == 10


def test_unstable_clock_blocks(store):
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series()}, mad_s=3000)
    outcome = service(adapter, store).collect_bars([Timeframe.M1], 60)
    assert outcome.status == "BLOCKED"
    assert "MAD" in outcome.reasons[0]


def test_unknown_clock_degrades_but_does_not_lose_data(store):
    """No fresh ticks (daily halt) → timestamps use the model, run is flagged."""
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series()}, offset=None)
    outcome = service(adapter, store).collect_bars([Timeframe.M1], 60)

    assert outcome.status == "DEGRADED"
    assert "clock_unverified" in outcome.runs[0].reason
    assert store.health()["bars"] == 60


def test_clean_collection_is_ok(store):
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series()})
    outcome = service(adapter, store).collect_bars([Timeframe.M1], 60)

    assert outcome.status == "OK"
    assert outcome.runs[0].inserted == 60
    assert adapter.detached is True
    assert store.health()["bars"] == 60


def test_missing_symbol_blocks_without_writes(store):
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series()}, specs=[])
    outcome = service(adapter, store).collect_bars([Timeframe.M1], 60)

    assert outcome.status == "BLOCKED"
    assert "NOT_FOUND" in outcome.reasons[0]
    assert store.health()["bars"] == 0


def test_symbol_metadata_drift_blocks(store):
    drifted = SymbolSpec(
        name="XAUUSD.", path=r"Pure\Spot Metals\Gold\XAUUSD.", trade_mode=4,
        digits=2, tick_size=0.01, contract_size=10.0, currency_profit="USD", visible=True,
    )
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series()}, specs=[drifted])
    outcome = service(adapter, store).collect_bars([Timeframe.M1], 60)

    assert outcome.status == "BLOCKED"
    assert "METADATA_MISMATCH" in outcome.reasons[0]
    assert store.health()["bars"] == 0


def test_real_account_is_refused(store):
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series()}, identity=dict(DEMO, trade_mode="REAL"))
    outcome = service(adapter, store).collect_bars([Timeframe.M1], 60)

    assert outcome.status == "BLOCKED"
    assert "REAL" in outcome.reasons[0]


def test_none_rates_is_failed(store):
    adapter = FakeMarketAdapter(rates_none=True)
    outcome = service(adapter, store).collect_bars([Timeframe.M1], 60)

    assert outcome.status == "FAILED"
    assert outcome.runs[0].reason == "copy_rates returned None"


def test_timeframes_report_independently(store):
    broken = series()
    del broken[20:23]
    adapter = FakeMarketAdapter(bars={Timeframe.M1: series(), Timeframe.M5: broken})
    outcome = service(adapter, store).collect_bars([Timeframe.M1, Timeframe.M5], 60)

    statuses = {run.timeframe: run.status for run in outcome.runs}
    assert statuses[Timeframe.M1] == "OK"
    assert statuses[Timeframe.M5] == "DEGRADED"
    assert outcome.status == "DEGRADED"


def test_gap_is_persisted(store):
    broken = series()
    del broken[10:13]
    adapter = FakeMarketAdapter(bars={Timeframe.M1: broken})
    service(adapter, store).collect_bars([Timeframe.M1], 60)

    conn = store._conn  # test-only access
    assert conn.execute("SELECT SUM(bars_missing) FROM data_gaps").fetchone()[0] == 3


def test_tick_window_beyond_limit_blocks_before_attach(store):
    adapter = FakeMarketAdapter()
    outcome = service(adapter, store, max_tick_window_h=1).collect_ticks(
        NOW - timedelta(hours=3), NOW
    )

    assert outcome.status == "BLOCKED"
    assert "max_tick_window_h" in outcome.reasons[0]
    assert adapter.attach_calls == 0


def test_ticks_are_stored_and_deduped(store):
    ticks = [
        MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1_800_000_000_000 + i,
                   bid=4000 + i * 0.01, ask=4000.2 + i * 0.01)
        for i in range(5)
    ]
    adapter = FakeMarketAdapter(ticks=ticks + ticks)
    outcome = service(adapter, store).collect_ticks(NOW - timedelta(minutes=30), NOW)

    assert outcome.status == "OK"
    assert outcome.runs[0].inserted == 5


def test_tick_capture_blocks_when_clock_is_unverified(store):
    """F-C: milliseconds evidence is never stored on an unverified clock."""
    ticks = [MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1_800_000_000_000,
                        bid=4000.0, ask=4000.2)]
    adapter = FakeMarketAdapter(ticks=ticks, offset=None)
    outcome = service(adapter, store).collect_ticks(NOW - timedelta(minutes=10), NOW)

    assert outcome.status == "BLOCKED"
    assert "clock_unverified" in outcome.reasons[0]
    assert store.health()["ticks"] == 0


def test_truncated_tick_window_is_degraded(store):
    ticks = [MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1_800_000_000_000 + i,
                        bid=4000.0, ask=4000.2) for i in range(5)]
    adapter = FakeMarketAdapter(ticks=ticks)
    outcome = service(adapter, store, tick_limit=5).collect_ticks(NOW - timedelta(minutes=10), NOW)

    assert outcome.status == "DEGRADED"
    assert "tick_window_truncated" in outcome.runs[0].reason


def test_crossed_quotes_degrade_ticks(store):
    ticks = [
        MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1_800_000_000_001, bid=4001.0, ask=4000.0),
        MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1_800_000_000_002, bid=4000.0, ask=4000.2),
    ]
    adapter = FakeMarketAdapter(ticks=ticks)
    outcome = service(adapter, store).collect_ticks(NOW - timedelta(minutes=5), NOW)

    assert outcome.status == "DEGRADED"
    assert "crossed_quotes:1" in outcome.runs[0].reason
