"""Adapter conversion: numpy-free dataclasses, None on API failure."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from guardian.adapters.mt5_market import (
    MAX_TICK_AGE_S,
    Mt5MarketAdapter,
    is_fresh_tick,
    tick_age_seconds,
)
from guardian.contracts.market import Timeframe
from guardian.domain.market.broker_clock import BrokerClock


class FakeMt5:
    TIMEFRAME_M1 = 1
    TIMEFRAME_H1 = 16385
    COPY_TICKS_ALL = 0

    def __init__(self, rows=None, tick_rows=None, live_tick_time=None):
        self._rows = rows
        self._tick_rows = tick_rows
        self._live_tick_time = live_tick_time
        self.last_tick_start = None
        self.tick_queries = 0

    def symbol_info_tick(self, symbol):
        source = self._live_tick_time
        if source is None:
            return None
        # Evaluated per call: a stamp frozen at construction cannot model a
        # moving clock and made the latency tests depend on the sample instant (A4).
        self.tick_queries += 1
        return SimpleNamespace(time=int(source() if callable(source) else source))

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return self._rows

    def copy_ticks_from(self, symbol, start, count, flags):
        self.last_tick_start = start
        return self._tick_rows


def test_rates_are_converted_to_dataclasses():
    rows = [
        {"time": 1_800_000_000, "open": 4000.0, "high": 4002.0, "low": 3999.0,
         "close": 4001.0, "tick_volume": 12, "spread": 20, "real_volume": 0.0}
    ]
    adapter = Mt5MarketAdapter()
    adapter._mt5 = FakeMt5(rows=rows)  # test seam

    bars = adapter.rates("XAUUSD.", Timeframe.M1, 10)
    assert bars is not None and len(bars) == 1
    assert bars[0].close == 4001.0
    assert bars[0].time_utc == BrokerClock().to_utc(1_800_000_000)
    assert bars[0].timeframe is Timeframe.M1


def test_rates_none_is_preserved():
    adapter = Mt5MarketAdapter()
    adapter._mt5 = FakeMt5(rows=None)
    assert adapter.rates("XAUUSD.", Timeframe.M1, 10) is None


def test_empty_rates_is_empty_list_not_none():
    adapter = Mt5MarketAdapter()
    adapter._mt5 = FakeMt5(rows=[])
    assert adapter.rates("XAUUSD.", Timeframe.M1, 10) == []


def test_ticks_are_converted_with_millisecond_time():
    ms = 1_800_000_000_123
    adapter = Mt5MarketAdapter()
    adapter._mt5 = FakeMt5(tick_rows=[
        {"time_msc": ms, "bid": 4000.0, "ask": 4000.2, "last": 0.0, "volume": 1, "flags": 6}
    ])

    ticks = adapter.ticks("XAUUSD.", datetime(2026, 11, 4, tzinfo=timezone.utc), 10)
    assert ticks is not None and len(ticks) == 1
    assert ticks[0].time_msc == ms
    assert ticks[0].spread_points == 0.2 or abs(ticks[0].spread_points - 0.2) < 1e-9


def test_tick_api_failure_is_none():
    adapter = Mt5MarketAdapter()
    adapter._mt5 = FakeMt5(tick_rows=None)
    assert adapter.ticks("XAUUSD.", datetime(2026, 11, 4, tzinfo=timezone.utc), 10) is None


def test_bar_times_are_converted_from_server_time_to_utc():
    """MT5 bar times are broker-server time; the adapter must normalise them."""
    rows = [
        {"time": 1_800_007_200, "open": 4000.0, "high": 4001.0, "low": 3999.0,
         "close": 4000.5, "tick_volume": 1, "spread": 10, "real_volume": 0.0}
    ]
    adapter = Mt5MarketAdapter()
    adapter._mt5 = FakeMt5(rows=rows)

    bars = adapter.rates("XAUUSD.", Timeframe.M1, 1)
    assert bars[0].time_utc == datetime.fromtimestamp(1_800_000_000, tz=timezone.utc)
    assert bars[0].time_utc == BrokerClock().to_utc(1_800_007_200)


def test_tick_window_is_requested_in_server_time_and_filtered_to_utc():
    """A2: the terminal reads a server-wall epoch; callers pass UTC."""
    window_start = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)  # winter: +2h server
    inside = int(datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)  # 10:00Z
    before = int(datetime(2026, 12, 1, 11, 55, tzinfo=timezone.utc).timestamp() * 1000)  # 09:55Z
    rows = [
        {"time_msc": inside, "bid": 4000.0, "ask": 4000.2, "last": 0.0, "volume": 1, "flags": 6},
        {"time_msc": before, "bid": 4000.0, "ask": 4000.2, "last": 0.0, "volume": 1, "flags": 6},
    ]
    fake = FakeMt5(tick_rows=rows)
    adapter = Mt5MarketAdapter()
    adapter._mt5 = fake

    ticks = adapter.ticks("XAUUSD.", window_start, 10)
    assert fake.last_tick_start == 1796126400  # 2026-12-01T12:00 server wall
    assert ticks is not None and len(ticks) == 1
    assert ticks[0].time_utc == window_start


def test_tick_window_request_follows_the_dst_model():
    """A2/A6: the wall epoch carries the seasonal offset; expected values are literals, not the formula."""
    for moment, expected in (
        (datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc), 1785589200),   # server 13:00 (+3 h)
        (datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc), 1796126400),  # server 12:00 (+2 h)
    ):
        fake = FakeMt5(tick_rows=[])
        adapter = Mt5MarketAdapter()
        adapter._mt5 = fake
        adapter.ticks("XAUUSD.", moment, 1)
        assert fake.last_tick_start == expected


def test_offset_estimator_uses_the_modelled_server_clock():
    """Audit F1b: tick.time is server time, so freshness must be server-relative."""
    import time as _time

    from guardian.domain.market.broker_clock import BrokerClock

    clock = BrokerClock()
    adapter = Mt5MarketAdapter(clock=clock)
    model_offset = clock.offset_for(datetime.now(timezone.utc))
    fake = FakeMt5(live_tick_time=lambda: int(_time.time()) + model_offset)
    adapter._mt5 = fake

    measured = adapter.estimate_server_offset("XAUUSD.", samples=3, pause_s=0.0)
    assert measured is not None
    offset, mad, samples = measured
    assert abs(offset - model_offset) <= 60
    assert samples >= 3
    assert mad <= 2


def test_tick_age_sign_convention():
    """A1: positive age means older than server-now; negative means ahead of it."""
    now = 1_700_000_000
    model = 7200
    server_now = now + model
    assert tick_age_seconds(server_now, now, model) == 0        # stamped at server-now
    assert tick_age_seconds(server_now - 1, now, model) == 1    # 1 s old
    assert tick_age_seconds(server_now + 1, now, model) == -1   # 1 s ahead (broker clock leads)
    assert tick_age_seconds(server_now - MAX_TICK_AGE_S, now, model) == MAX_TICK_AGE_S
    assert tick_age_seconds(server_now + MAX_TICK_AGE_S, now, model) == -MAX_TICK_AGE_S


def test_fresh_tick_boundaries_are_symmetric():
    """A1/A3: the bound is a tolerance on |age|, not a one-sided lead."""
    now = 1_700_000_000
    model = 7200
    server_now = now + model
    for age in (0, 1, 2, MAX_TICK_AGE_S):
        assert is_fresh_tick(server_now - age, now, model) is True, f"{age}s old must pass"
        assert is_fresh_tick(server_now + age, now, model) is True, f"{age}s ahead must pass"
    for age in (MAX_TICK_AGE_S + 1, 30):
        assert is_fresh_tick(server_now - age, now, model) is False, f"{age}s old must fail"
        assert is_fresh_tick(server_now + age, now, model) is False, f"{age}s ahead must fail"


def test_invalid_tick_timestamp_is_never_fresh():
    now = 1_700_000_000
    model = 7200
    assert is_fresh_tick(0, now, model) is False
    assert is_fresh_tick(-1, now, model) is False


def test_tick_far_in_the_future_is_rejected():
    """A3: a far-future tick has a *negative* age and is refused by magnitude."""
    now = 1_700_000_000
    model = 7200
    server_now = now + model
    assert tick_age_seconds(server_now + 30, now, model) == -30
    assert is_fresh_tick(server_now + 30, now, model) is False


def test_raw_utc_tick_is_rejected():
    """A tick read as raw UTC sits one model offset away from server-now."""
    now = 1_700_000_000
    model = 7200
    assert tick_age_seconds(now, now, model) == model
    assert is_fresh_tick(now, now, model) is False


class _AdvancingMt5(FakeMt5):
    """Deterministic advancing clock: each sample is 1 s newer than the last."""

    def __init__(self, start_time: int):
        super().__init__()
        self._t = int(start_time)

    def symbol_info_tick(self, symbol):
        class _T:
            pass

        tick = _T()
        tick.time = self._t
        self._t += 1
        return tick


def test_offset_estimator_accepts_a_one_second_old_tick():
    """A4: the stamp advances per call, so the 1 s latency genuinely reaches the gate."""
    import time as _time

    from guardian.domain.market.broker_clock import BrokerClock

    clock = BrokerClock()
    offset = clock.offset_for(datetime.now(timezone.utc))
    adapter = Mt5MarketAdapter(clock=clock)
    adapter._mt5 = _AdvancingMt5(int(_time.time()) + offset - 1)

    measured = adapter.estimate_server_offset("XAUUSD.", samples=3, pause_s=0.0)
    assert measured is not None
    assert abs(measured[0] - offset) <= 60


def test_offset_estimator_rejects_a_stale_tick():
    import time as _time

    from guardian.domain.market.broker_clock import BrokerClock

    clock = BrokerClock()
    offset = clock.offset_for(datetime.now(timezone.utc))
    adapter = Mt5MarketAdapter(clock=clock)
    adapter._mt5 = _AdvancingMt5(int(_time.time()) + offset - 30)

    assert adapter.estimate_server_offset("XAUUSD.", samples=3, pause_s=0.0) is None


def test_offset_estimator_accepts_a_tick_ahead_of_the_model():
    """A1: the live broker clock leads the model by ~1.5 s; a lead must not be rejected."""
    import time as _time

    from guardian.domain.market.broker_clock import BrokerClock

    clock = BrokerClock()
    offset = clock.offset_for(datetime.now(timezone.utc))
    adapter = Mt5MarketAdapter(clock=clock)
    adapter._mt5 = _AdvancingMt5(int(_time.time()) + offset + 1)

    measured = adapter.estimate_server_offset("XAUUSD.", samples=3, pause_s=0.0)
    assert measured is not None
    assert abs(measured[0] - offset) <= 60


def test_offset_estimator_rejects_a_far_future_tick():
    import time as _time

    from guardian.domain.market.broker_clock import BrokerClock

    clock = BrokerClock()
    offset = clock.offset_for(datetime.now(timezone.utc))
    adapter = Mt5MarketAdapter(clock=clock)
    adapter._mt5 = _AdvancingMt5(int(_time.time()) + offset + 30)

    assert adapter.estimate_server_offset("XAUUSD.", samples=3, pause_s=0.0) is None


def test_conversion_uses_the_dst_model_across_the_switch():
    """A6: one authoritative clock — a constant measured offset would shift history."""
    adapter = Mt5MarketAdapter()
    summer = int(datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc).timestamp())
    winter = int(datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc).timestamp())
    assert adapter.to_utc(summer + 3 * 3600) == datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    assert adapter.to_utc(winter + 2 * 3600) == datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)


def test_broker_clock_rejects_a_offset_the_model_does_not_explain():
    from guardian.domain.market.broker_clock import BrokerClock

    clock = BrokerClock()
    winter = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
    assert clock.matches(7200, winter) is True
    assert clock.matches(10800, winter) is False
