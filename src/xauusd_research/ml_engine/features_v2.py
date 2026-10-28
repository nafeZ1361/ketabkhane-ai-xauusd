"""Feature engineering v2 — richer, strictly non-repainting windowed features.

Motivation (honest research log): the v1 point-in-time feature set (7 scalar
features) produced a RandomForest that never beat the majority baseline on
walk-forward folds (accuracy ~= 0.50-0.52 vs baseline ~= 0.505). The verdict
was: *the geometry of the problem was under-specified*, not that gold is
unlearnable. v2 changes two things:

1. **Sequence features**: models receive a fixed-length window of per-bar
   normalized channels (returns, ranges, body ratios, volume z-score), so
   tree ensembles and DNNs can see temporal shape, not just 7 aggregates.
2. **Triple-barrier labels** (Lopez de Prado): label = sign of the first
   barrier touched by close within ``horizon`` bars, where the up/down
   barriers are k * ATR(i) away from entry. Neutral outcomes are dropped
   (excluded from supervised training), which converts an unbalanced
   direction problem into a cleaner event-classification problem.

Leakage contract (enforced in code + tests):
- channel at bar ``j`` uses only candles ``[j-lookback .. j]``;
- the window for sample ``i`` ends exactly at ``i``;
- labels may look ahead (that is their definition) but the trainer applies
  an embargo >= horizon between train and test slices.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from xauusd_research.schema import Candle

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WARMUP_V2 = 60          # history needed before the first valid sample
WINDOW_LEN = 32         # bars per sequence sample
N_CHANNELS = 4
CHANNEL_NAMES = ("ret", "range_ratio", "body_ratio", "vol_z")

LABEL_HORIZON_V2 = 24   # triple-barrier max holding length (bars)
ATR_LEN = 14
ATR_LONG_LEN = 50
K_ATR_UP = 1.0          # upper barrier distance in ATR units
K_ATR_DOWN = 1.0        # lower barrier distance in ATR units


@dataclass(frozen=True)
class LabelCounts:
    """Dataset composition evidence — recorded in metrics for honesty."""

    long: int
    short: int
    neutral_dropped: int

    @property
    def kept(self) -> int:
        return self.long + self.short


def _atr_series(candles: Sequence[Candle]) -> np.ndarray:
    n = len(candles)
    tr = np.empty(n, dtype=float)
    tr[0] = candles[0].high - candles[0].low
    for i in range(1, n):
        c = candles[i]
        pc = candles[i - 1].close
        tr[i] = max(c.high - c.low, abs(c.high - pc), abs(c.low - pc))
    # Simple moving average of TR (rolling, causal).
    atr = np.full(n, np.nan)
    cs = np.cumsum(np.insert(tr, 0, 0.0))
    for i in range(ATR_LEN - 1, n):
        atr[i] = (cs[i + 1] - cs[i + 1 - ATR_LEN]) / ATR_LEN
    return atr


def build_channel_matrix(candles: Sequence[Candle]) -> np.ndarray:
    """Return an ``(n_bars, N_CHANNELS)`` causal feature matrix.

    Row ``i`` depends only on candles ``[i-WARMUP_V2 .. i]``.
    """
    n = len(candles)
    closes = np.fromiter((c.close for c in candles), dtype=float, count=n)
    highs = np.fromiter((c.high for c in candles), dtype=float, count=n)
    lows = np.fromiter((c.low for c in candles), dtype=float, count=n)
    opens = np.fromiter((c.open for c in candles), dtype=float, count=n)
    vols = np.fromiter((float(c.tickvol) for c in candles), dtype=float, count=n)
    atr = _atr_series(candles)

    mat = np.zeros((n, N_CHANNELS), dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        ret = np.zeros(n)
        ret[1:] = (closes[1:] - closes[:-1]) / closes[:-1]
        rng = np.where(closes > 0, (highs - lows) / closes, 0.0)
        body = np.where(closes > 0, (closes - opens) / closes, 0.0)

    # vol z-score over trailing 50 bars (causal rolling std).
    vol_mean = np.full(n, np.nan)
    vol_std = np.full(n, np.nan)
    w = 50
    cs = np.cumsum(np.insert(vols, 0, 0.0))
    csq = np.cumsum(np.insert(vols * vols, 0, 0.0))
    for i in range(w - 1, n):
        m = (cs[i + 1] - cs[i + 1 - w]) / w
        var = max((csq[i + 1] - csq[i + 1 - w]) / w - m * m, 0.0)
        vol_mean[i] = m
        vol_std[i] = var ** 0.5

    for i in range(n):
        a = atr[i] if not np.isnan(atr[i]) and atr[i] > 0 else 1e-9
        vz = 0.0
        if not np.isnan(vol_std[i]) and vol_std[i] > 1e-12:
            vz = float(min(max((vols[i] - vol_mean[i]) / vol_std[i], -8.0), 8.0))
        mat[i] = (
            float(np.clip(ret[i] / a * 10.0, -8.0, 8.0)),      # return / ATR scale
            float(rng[i]),                                      # bar range ratio
            float(body[i]),                                     # body ratio
            vz,                                                 # volume z-score
        )
    return mat


def triple_barrier_label(
    candles: Sequence[Candle],
    index: int,
    atr: np.ndarray,
    horizon: int = LABEL_HORIZON_V2,
    k_up: float = K_ATR_UP,
    k_down: float = K_ATR_DOWN,
) -> int | None:
    """First-barrier-touched label. Returns 1 (LONG), 0 (SHORT), or -1 neutral.

    ``None`` when the future window is incomplete (end of series).
    Training-only function — never called from inference paths.
    """
    n = len(candles)
    end = index + horizon
    if end >= n:
        return None
    base = candles[index].close
    a = atr[index]
    if base <= 0 or np.isnan(a) or a <= 0:
        return None
    up = base + k_up * a
    down = base - k_down * a
    for j in range(index + 1, end + 1):
        c = candles[j].close
        if c >= up:
            return 1
        if c <= down:
            return 0
    return -1  # neither barrier touched within horizon -> neutral, dropped


def build_dataset_v2(
    candles: Sequence[Candle],
    horizon: int = LABEL_HORIZON_V2,
    k_up: float = K_ATR_UP,
    k_down: float = K_ATR_DOWN,
    stride: int = 1,
) -> tuple[np.ndarray, np.ndarray, LabelCounts]:
    """Assemble ``(X, y, counts)`` where X has shape ``(m, WINDOW_LEN*N_CHANNELS)``.

    Samples near the end of the series (incomplete label window) are skipped.
    """
    n = len(candles)
    if n < WARMUP_V2 + WINDOW_LEN + horizon + 1:
        return (np.zeros((0, WINDOW_LEN * N_CHANNELS)),
                np.zeros(0, dtype=int),
                LabelCounts(0, 0, 0))
    mat = build_channel_matrix(candles)
    atr = _atr_series(candles)

    xs: list[np.ndarray] = []
    ys: list[int] = []
    neutral = 0
    for i in range(WARMUP_V2 + WINDOW_LEN - 1, n - horizon, max(1, stride)):
        lab = triple_barrier_label(candles, i, atr, horizon, k_up, k_down)
        if lab is None:
            continue
        if lab == -1:
            neutral += 1
            continue
        win = mat[i - WINDOW_LEN + 1: i + 1]          # ends exactly at i
        xs.append(win.reshape(-1))
        ys.append(lab)
    X = np.asarray(xs, dtype=float) if xs else np.zeros((0, WINDOW_LEN * N_CHANNELS))
    y = np.asarray(ys, dtype=int) if ys else np.zeros(0, dtype=int)
    counts = LabelCounts(long=int((y == 1).sum()), short=int((y == 0).sum()),
                         neutral_dropped=neutral)
    return X, y, counts
