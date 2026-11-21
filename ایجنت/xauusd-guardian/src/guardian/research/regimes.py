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
    if lookback < 2 or volatility_lookback < lookback:
        raise RegimeError("invalid lookback windows")
    for name, value in (("trend_efficiency_threshold", trend_efficiency_threshold),
                        ("high_volatility_multiple", high_volatility_multiple)):
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise RegimeError(f"{name} must be a positive finite Decimal")
    if trend_efficiency_threshold > 1 or high_volatility_multiple <= 1:
        raise RegimeError("thresholds outside supported range")
    needed = volatility_lookback + lookback + 1
    if len(bars) < needed:
        raise RegimeError(f"insufficient closed bars: need {needed}, got {len(bars)}")
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
    hist_start = current_start - volatility_lookback
    for end in range(hist_start + lookback, current_start + 1):
        start = end - lookback
        historical_atrs.append(sum((tr(i) for i in range(start, end)), Decimal(0)) / Decimal(lookback))
    baseline = Decimal(str(median(historical_atrs)))
    closes = [Decimal(str(b.close)) for b in bars[current_start - 1:]]
    path = sum((abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))), Decimal(0))
    net = closes[-1] - closes[0]
    efficiency = abs(net) / path if path else Decimal(0)
    if baseline > 0 and current_atr > baseline * high_volatility_multiple:
        regime = MarketRegime.HIGH_VOLATILITY
    elif efficiency >= trend_efficiency_threshold and net > 0:
        regime = MarketRegime.TREND_UP
    elif efficiency >= trend_efficiency_threshold and net < 0:
        regime = MarketRegime.TREND_DOWN
    else:
        regime = MarketRegime.RANGE
    return RegimeReport(regime, efficiency, current_atr, baseline)
