"""Strategy definitions and the moving-average crossover signal."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategySpec:
    name: str
    fast: int
    slow: int


STRATEGIES = (
    StrategySpec("ma_5_20", 5, 20),
    StrategySpec("ma_10_50", 10, 50),
    StrategySpec("ma_20_100", 20, 100),
)
STRATEGY_BY_NAME = {spec.name: spec for spec in STRATEGIES}


def sma(values, window):
    if window <= 0:
        raise ValueError("window must be positive")
    out = [None] * len(values)
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= window:
            total -= values[i - window]
        if i >= window - 1:
            out[i] = total / window
    return out


def signals(candles, spec):
    """+1 on a bullish cross, -1 on a bearish cross, 0 otherwise."""
    closes = [c.close for c in candles]
    fast = sma(closes, spec.fast)
    slow = sma(closes, spec.slow)
    out = [0] * len(closes)
    for i in range(1, len(closes)):
        if fast[i] is None or slow[i] is None or fast[i - 1] is None or slow[i - 1] is None:
            continue
        if fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]:
            out[i] = 1
        elif fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]:
            out[i] = -1
    return out