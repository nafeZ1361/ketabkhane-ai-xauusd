"""Fractional Differentiation for Financial Time Series.

Achieves stationarity while preserving memory and long-term trend features.
"""
from __future__ import annotations


def get_weights(d: float, size: int) -> list[float]:
    """Generates binomial series weights for memory order d."""
    w = [1.0]
    for k in range(1, size):
        w.append(-w[-1] / k * (d - k + 1))
    return w


def frac_diff_ffd(series: list[float], d: float, thres: float = 1e-4) -> list[float | None]:
    """Fixed-width window fractional differentiation."""
    weights = get_weights(d, len(series))
    weights = [w for w in weights if abs(w) >= thres]
    k = len(weights)

    out = [None] * len(series)
    for i in range(k - 1, len(series)):
        val = sum(weights[j] * series[i - j] for j in range(k))
        out[i] = round(val, 6)
    return out
