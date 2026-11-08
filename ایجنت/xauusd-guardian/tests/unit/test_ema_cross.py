"""S2: EMA correctness, ordering, warmup, and the look-ahead property."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal

import pytest

from guardian.contracts.market import MarketBar, Timeframe
from guardian.contracts.signals import Direction, SignalError
from guardian.domain.strategy import ema_cross

T0 = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
NOW = T0 + timedelta(minutes=5 * 120 + 5)  # after the last fixture bar closes



class _NeutralTZ(tzinfo):
    def utcoffset(self, dt):
        return None

    def dst(self, dt):
        return None


class _NonTimedeltaTZ(tzinfo):
    def utcoffset(self, dt):
        return "not-a-timedelta"

    def dst(self, dt):
        return None


class _OutOfRangeTZ(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=25)

    def dst(self, dt):
        return None


@pytest.mark.parametrize(
    "zone",
    [_NeutralTZ(), _NonTimedeltaTZ(), _OutOfRangeTZ()],
    ids=["neutral-offset", "non-timedelta-offset", "out-of-range-offset"],
)
def test_now_requires_valid_utc_offset(zone):
    moment = datetime(2026, 11, 5, 12, 0, tzinfo=zone)
    with pytest.raises(SignalError, match="valid UTC offset"):
        ema_cross.evaluate(series(), now=moment)


def bar(i: int, close: float) -> MarketBar:
    return MarketBar(symbol="XAUUSD.", timeframe=Timeframe.M5, time_utc=T0 + timedelta(minutes=5 * i),
                     open=close, high=close + 1, low=close - 1, close=close, tick_volume=1)


def series(n: int = 120) -> list[MarketBar]:
    prices = [100 + i for i in range(60)] + [160 - 3 * (i - 60) for i in range(60, n)]
    return [bar(i, float(p)) for i, p in enumerate(prices)]


def test_ema_seed_and_values():
    values = [Decimal(i) for i in range(1, 6)]
    out = ema_cross.ema(values, 3)
    assert out[:2] == [None, None]
    assert out[2] == Decimal(2)  # SMA of 1,2,3
    k = Decimal(2) / Decimal(4)
    assert out[3] == (Decimal(4) - Decimal(2)) * k + Decimal(2)


def test_ema_warmup_is_none():
    assert ema_cross.ema([Decimal(1)] * 10, 20) == [None] * 10
    with pytest.raises(SignalError):
        ema_cross.ema([Decimal(1)], 0)


def test_signals_only_after_warmup_and_are_valid():
    signals = ema_cross.evaluate(series(), now=NOW)
    assert signals, "synthetic reversal must produce at least one cross"
    assert all(s.bar_time_utc >= series()[50].time_utc for s in signals)
    assert all(s.direction in (Direction.LONG, Direction.SHORT) for s in signals)
    assert all(s.reason_code in ("CROSS_UP", "CROSS_DOWN") for s in signals)


def test_reversal_produces_a_short():
    assert any(s.direction is Direction.SHORT for s in ema_cross.evaluate(series(), now=NOW))


def test_look_ahead_property():
    """Truncating the tail must not change any historical signal."""
    full = series()
    for cut in (60, 75, 90, 110):
        partial = ema_cross.evaluate(full[:cut], now=NOW)
        expected = [s for s in ema_cross.evaluate(full, now=NOW) if s.bar_time_utc <= full[cut - 1].time_utc]
        assert partial == expected, f"look-ahead detected at cut={cut}"


def test_non_monotonic_series_is_refused():
    bars = series(60)
    bars[10], bars[11] = bars[11], bars[10]
    with pytest.raises(SignalError):
        ema_cross.evaluate(bars, now=NOW)


def test_replay_is_deterministic():
    """S3: the same bars must yield byte-identical signals on every run."""
    import hashlib

    bars = series()
    signals = ema_cross.evaluate(bars, now=NOW)
    assert len(signals) >= 1, "the fixture must exercise a real crossing"
    def digest(items):
        h = hashlib.sha256()
        for s in items:
            h.update(f"{s.bar_time_utc.isoformat()}|{s.direction.value}|{s.strength}|{s.reason_code}\n".encode())
        return h.hexdigest()
    first = digest(signals)
    assert digest(ema_cross.evaluate(bars, now=NOW)) == first


def test_forming_bar_is_refused():
    bars = series()
    with pytest.raises(SignalError, match="forming"):
        ema_cross.evaluate(bars, now=bars[-1].time_utc + timedelta(minutes=1))
    ema_cross.evaluate(bars, now=bars[-1].time_utc + timedelta(minutes=5))


def test_incomplete_series_is_refused():
    with pytest.raises(SignalError):
        ema_cross.evaluate(series()[:40], now=NOW)
