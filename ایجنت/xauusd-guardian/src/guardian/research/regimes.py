"""Past-only market regime classification over closed OHLC bars."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from statistics import median
from typing import Sequence
from guardian.contracts.market import MarketBar


class RegimeError(ValueError):
    pass


class MarketRegime(str, Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


@dataclass(frozen=True, slots=True)
class RegimeReport:
    regime: MarketRegime
    efficiency_ratio: Decimal
    current_atr: Decimal
    historical_median_atr: Decimal


def classify_regime(
    bars: Sequence[MarketBar],
    *,
    lookback: int = 20,
    volatility_lookback: int = 100,
    trend_efficiency_threshold: Decimal = Decimal("0.35"),
    high_volatility_multiple: Decimal = Decimal("1.5"),
) -> RegimeReport:
    if (isinstance(lookback, bool) or not isinstance(lookback, int)
            or isinstance(volatility_lookback, bool) or not isinstance(volatility_lookback, int)
            or lookback < 2 or volatility_lookback < lookback):
        raise RegimeError("invalid lookback windows")
    for name, value in (("trend_efficiency_threshold", trend_efficiency_threshold),
                        ("high_volatility_multiple", high_volatility_multiple)):
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise RegimeError(f"{name} must be a positive finite Decimal")
    if trend_efficiency_threshold > 1 or high_volatility_multiple <= 1:
        raise RegimeError("thresholds outside supported range")
    # Need volatility_lookback complete historical ATR windows, plus the current window.
    needed = volatility_lookback + (2 * lookback)
    if len(bars) < needed:
        raise RegimeError(f"insufficient closed bars: need {needed}, got {len(bars)}")
    for bar in bars:
        prices = tuple(Decimal(str(value)) for value in (bar.open, bar.high, bar.low, bar.close))
        if any(not value.is_finite() or value <= 0 for value in prices):
            raise RegimeError("bar prices must be positive and finite")
        if prices[1] < max(prices[0], prices[3]) or prices[2] > min(prices[0], prices[3]) or prices[1] < prices[2]:
            raise RegimeError("bar OHLC relationship is invalid")
    if any(bars[i].time_utc >= bars[i + 1].time_utc for i in range(len(bars) - 1)):
        raise RegimeError("bars must be strictly increasing")
    if any(b.symbol != bars[0].symbol or b.timeframe != bars[0].timeframe for b in bars):
        raise RegimeError("bars must share symbol and timeframe")

    def tr(i: int) -> Decimal:
        bar = bars[i]
        high, low, prev_close = Decimal(str(bar.high)), Decimal(str(bar.low)), Decimal(str(bars[i - 1].close))
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    current_start = len(bars) - lookback
    current_atr = sum((tr(i) for i in range(current_start, len(bars))), Decimal(0)) / Decimal(lookback)
    historical_atrs = []
    first_start = current_start - volatility_lookback - lookback
    last_start = current_start - lookback
    for start in range(first_start, last_start):
        historical_atrs.append(
            sum((tr(i) for i in range(start + 1, start + lookback + 1)), Decimal(0))
            / Decimal(lookback)
        )
    baseline = Decimal(str(median(historical_atrs)))
    closes = [Decimal(str(b.close)) for b in bars[current_start - 1:]]
    path = sum((abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))), Decimal(0))
    net = closes[-1] - closes[0]
    efficiency = abs(net) / path if path else Decimal(0)
    if (baseline == 0 and current_atr > 0) or (baseline > 0 and current_atr > baseline * high_volatility_multiple):
        regime = MarketRegime.HIGH_VOLATILITY
    elif efficiency >= trend_efficiency_threshold and net > 0:
        regime = MarketRegime.TREND_UP
    elif efficiency >= trend_efficiency_threshold and net < 0:
        regime = MarketRegime.TREND_DOWN
    else:
        regime = MarketRegime.RANGE
    return RegimeReport(regime, efficiency, current_atr, baseline)
