"""EMA cross reference strategy (Phase 3, S2). Closed bars only; Decimal math."""

from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Sequence

from guardian.contracts.market import MarketBar, Timeframe
from guardian.contracts.signals import Direction, Signal, SignalError, StrategySpec

from datetime import datetime, timezone

FAST = 20
SLOW = 50
MINUTES = {Timeframe.M1: 1, Timeframe.M5: 5, Timeframe.M15: 15, Timeframe.H1: 60, Timeframe.H4: 240}
SPEC = StrategySpec(id="ema_cross_v1", version="1", params={"fast": Decimal(FAST), "slow": Decimal(SLOW)}, warmup_bars=SLOW)


def ema(values: Sequence[Decimal], period: int) -> list[Decimal | None]:
    """EMA seeded with the SMA of the first ``period`` values; None before that."""
    if period <= 0:
        raise SignalError("period must be positive")
    if len(values) < period:
        return [None] * len(values)
    k = Decimal(2) / Decimal(period + 1)
    out: list[Decimal | None] = [None] * (period - 1)
    seed = sum(values[:period]) / Decimal(period)
    out.append(seed)
    for value in values[period:]:
        seed = (value - seed) * k + seed
        out.append(seed)
    return out


def evaluate(bars: Sequence[MarketBar], strategy_id: str = SPEC.id, *, now: datetime) -> list[Signal]:
    """Signals for every bar where fast crosses slow. Bar i uses bars[0..i] only.

    The caller must pass closed bars, in ascending time order. A non-monotonic
    series is refused rather than silently re-sorted.
    """
    if len(bars) < SLOW:
        raise SignalError(f"insufficient bars: need {SLOW}, got {len(bars)}")
    moment = now
    if moment.tzinfo is None:
        raise SignalError("now must be timezone-aware")
    for bar in bars:
        close_at = bar.time_utc + timedelta(minutes=MINUTES[bar.timeframe])
        if close_at > moment:
            raise SignalError(f"bar {bar.time_utc.isoformat()} is still forming at {moment.isoformat()}")
    if any(bars[i].time_utc >= bars[i + 1].time_utc for i in range(len(bars) - 1)):
        raise SignalError("bars must be strictly increasing in time")
    closes = [Decimal(str(bar.close)) for bar in bars]
    fast = ema(closes, FAST)
    slow = ema(closes, SLOW)
    out: list[Signal] = []
    for i in range(1, len(bars)):
        if fast[i] is None or slow[i] is None or fast[i - 1] is None or slow[i - 1] is None:
            continue
        prev, now = fast[i - 1] - slow[i - 1], fast[i] - slow[i]
        if prev <= 0 < now:
            direction, reason = Direction.LONG, "CROSS_UP"
        elif prev >= 0 > now:
            direction, reason = Direction.SHORT, "CROSS_DOWN"
        else:
            continue
        out.append(
            Signal(
                symbol=bars[i].symbol,
                timeframe=bars[i].timeframe.value,
                bar_time_utc=bars[i].time_utc,
                direction=direction,
                strength=min(Decimal(1), abs(now) / (abs(prev) + abs(now)) if (abs(prev) + abs(now)) else Decimal(0)),
                strategy_id=strategy_id,
                reason_code=reason,
            )
        )
    return out
