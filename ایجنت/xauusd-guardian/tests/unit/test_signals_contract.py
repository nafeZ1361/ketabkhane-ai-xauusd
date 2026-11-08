"""S1: signal contracts reject ambiguity and non-Decimal values."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from guardian.contracts.signals import Direction, Signal, SignalError, SignalRun, StrategySpec

T = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def sig(**kw):
    base = dict(symbol="XAUUSD.", timeframe="M5", bar_time_utc=T, direction=Direction.LONG,
                strength=Decimal("0.5"), strategy_id="ema_cross_v1", reason_code="CROSS_UP")
    base.update(kw)
    return Signal(**base)


def test_valid_signal_is_accepted():
    assert sig().direction is Direction.LONG


@pytest.mark.parametrize("field,value", [
    ("bar_time_utc", datetime(2026, 11, 5, 12, 0)),
    ("symbol", ""),
    ("reason_code", ""),
    ("direction", "LONG"),
    ("strength", 0.5),
    ("strength", Decimal("1.1")),
])
def test_invalid_signal_is_refused(field, value):
    with pytest.raises(SignalError):
        sig(**{field: value})


def test_params_must_be_decimal():
    with pytest.raises(SignalError):
        StrategySpec(id="s", version="1", params={"fast": 20}, warmup_bars=50)
    assert StrategySpec(id="s", version="1", params={"fast": Decimal(20)}, warmup_bars=50).warmup_bars == 50


def test_run_window_must_be_ordered():
    with pytest.raises(SignalError):
        SignalRun(run_id="r", strategy_id="s", timeframe="M5", from_utc=T, to_utc=T, bars_seen=0, signals=0)


def test_all_guards_raise_signal_error():
    """Every boundary must surface as SignalError, never TypeError/InvalidOperation."""
    from decimal import Decimal as D
    cases = [
        lambda: sig(strength=D("NaN")),
        lambda: sig(strength=D("Infinity")),
        lambda: sig(strength=D("-0.1")),
        lambda: sig(symbol="   "),
        lambda: sig(timeframe=""),
        lambda: sig(strategy_id="  "),
        lambda: StrategySpec(id="s", version="1", params=None, warmup_bars=0),
        lambda: StrategySpec(id="s", version="1", params={"nope": D(1)}, warmup_bars=0),
        lambda: StrategySpec(id="s", version="1", params={"fast": D("NaN")}, warmup_bars=0),
        lambda: SignalRun(run_id="", strategy_id="s", timeframe="M5", from_utc=T, to_utc=T, bars_seen=0, signals=0),
        lambda: SignalRun(run_id="r", strategy_id="s", timeframe="  ", from_utc=T, to_utc=T, bars_seen=0, signals=0),
        lambda: SignalRun(run_id="r", strategy_id="s", timeframe="M5", from_utc=T.replace(tzinfo=None), to_utc=T, bars_seen=0, signals=0),
    ]
    for build in cases:
        with pytest.raises(SignalError):
            build()
