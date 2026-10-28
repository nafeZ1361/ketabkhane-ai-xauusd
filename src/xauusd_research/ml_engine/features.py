"""Feature engineering for the ML layer (strictly non-repainting).

Every feature at index ``i`` is computed from candles ``[0 .. i]`` only.
The label helpers are the *only* place that peeks into the future, and they
are used exclusively at training time (never inside inference paths).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from xauusd_research.schema import Candle

FEATURE_NAMES = (
    "atr_ratio_14_50",
    "slope_norm_20",
    "range_compression_20",
    "autocorr_lag1_20",
    "ret_1",
    "ret_5",
    "vol_zscore_50",
)


@dataclass(frozen=True)
class FeatureWindow:
    """Minimum history required before features become meaningful."""

    warmup: int = 50


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _true_range(candles: Sequence[Candle]) -> list[float]:
    trs: list[float] = []
    prev_close = None
    for c in candles:
        if prev_close is None:
            trs.append(c.high - c.low)
        else:
            trs.append(max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close)))
        prev_close = c.close
    return trs


def compute_features(candles: Sequence[Candle], index: int) -> tuple[float, ...] | None:
    """Return the feature vector for ``candles[index]`` using history up to and
    including ``index`` — or ``None`` when the warm-up window is incomplete."""
    if index < WARMUP:
        return None
    window = candles[max(0, index - 49): index + 1]
    n = len(window)
    closes = [c.close for c in window]
    tail_candles = window[-20:]

    trs = _true_range(window)
    atr_short = _mean(trs[-14:]) if n >= 14 else 0.0
    atr_long = _mean(trs) if n >= 50 else 0.0
    atr_ratio = atr_short / atr_long if atr_long > 0 else 1.0

    # Normalized OLS slope over the last 20 closes.
    tail = closes[-20:]
    k = len(tail)
    mean_p = _mean(tail)
    slope_norm = 0.0
    if k >= 2 and mean_p > 0:
        sum_x = k * (k - 1) / 2.0
        sum_xx = k * (k - 1) * (2 * k - 1) / 6.0
        sum_y = sum(tail)
        sum_xy = sum(j * tail[j] for j in range(k))
        denom = k * sum_xx - sum_x * sum_x
        slope = (k * sum_xy - sum_x * sum_y) / denom if abs(denom) > 1e-12 else 0.0
        slope_norm = slope / mean_p

    highest = max(c.high for c in tail_candles)
    lowest = min(c.low for c in tail_candles)
    range_comp = (highest - lowest) / atr_short if atr_short > 0 else 1.0

    returns = [
        (tail[j] - tail[j - 1]) / tail[j - 1]
        for j in range(1, k)
        if tail[j - 1] > 0
    ]
    autocorr = 0.0
    if len(returns) >= 5:
        mean_r = _mean(returns)
        devs = [r - mean_r for r in returns]
        var = sum(d * d for d in devs)
        if var > 1e-12:
            cov = sum(devs[j] * devs[j - 1] for j in range(1, len(devs)))
            autocorr = cov / var

    ret_1 = returns[-1] if returns else 0.0
    ret_5 = (closes[-1] - closes[-6]) / closes[-6] if n >= 6 and closes[-6] > 0 else 0.0

    vols = [c.tickvol for c in window]
    vol_mean = _mean(vols)
    vol_var = _mean([(v - vol_mean) ** 2 for v in vols])
    vol_z = (vols[-1] - vol_mean) / (vol_var ** 0.5) if vol_var > 1e-12 else 0.0

    return (
        round(atr_ratio, 6),
        round(slope_norm, 8),
        round(range_comp, 6),
        round(autocorr, 6),
        round(ret_1, 8),
        round(ret_5, 8),
        round(vol_z, 6),
    )


WARMUP = 50


def make_labels(
    candles: Sequence[Candle],
    index: int,
    horizon: int = 20,
    threshold: float = 0.001,
) -> int | None:
    """Training-only label: sign of the forward ``horizon``-bar return beyond
    ``threshold``. Returns ``None`` near the end of the series.

    LONG=1, SHORT=0, FLAT/neutral=-1 (excluded from supervised training).
    """
    future_index = index + horizon
    if future_index >= len(candles):
        return None
    base = candles[index].close
    if base <= 0:
        return None
    fwd_ret = (candles[future_index].close - base) / base
    if fwd_ret > threshold:
        return 1
    if fwd_ret < -threshold:
        return 0
    return -1


def build_dataset(
    candles: Sequence[Candle],
    horizon: int = 20,
    threshold: float = 0.001,
    stride: int = 1,
) -> tuple[list[tuple[float, ...]], list[int]]:
    """Vectorised dataset builder used by the trainer (no leakage: features use
    bars <= i, labels use exactly bars i..i+horizon which are removed by the
    embargo applied by the caller's walk-forward splitter)."""
    xs: list[tuple[float, ...]] = []
    ys: list[int] = []
    for i in range(WARMUP, len(candles) - horizon, max(1, stride)):
        feats = compute_features(candles, i)
        if feats is None:
            continue
        label = make_labels(candles, i, horizon=horizon, threshold=threshold)
        if label is None or label == -1:
            continue
        xs.append(feats)
        ys.append(label)
    return xs, ys
