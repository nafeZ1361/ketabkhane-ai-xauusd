"""Adaptive Market Regime & Session Filter for XAUUSD.

Distinguishes between trending, choppy range, and high-risk news spike regimes.
"""
from __future__ import annotations


def calculate_atr(candles, period=14):
    """True Range & Average True Range calculation."""
    if len(candles) < period + 1:
        return [None] * len(candles)

    tr = [0.0]
    for i in range(1, len(candles)):
        c = candles[i]
        prev_close = candles[i - 1].close
        val = max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close))
        tr.append(val)

    atr = [None] * len(candles)
    initial_atr = sum(tr[1:period + 1]) / period
    atr[period] = initial_atr
    for i in range(period + 1, len(candles)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def is_major_session(hour_utc: int) -> bool:
    """London & New York market hours (07:00 UTC to 20:00 UTC)."""
    return 7 <= hour_utc <= 20
