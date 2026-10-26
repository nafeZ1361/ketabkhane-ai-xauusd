"""Meta-Labeling and Triple Barrier Method for XAUUSD.

Reverse-engineered from Marcos Lopez de Prado (Advances in Financial Machine Learning).
Filters primary signals to eliminate low-probability trades and reduce spread friction.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BarrierEvent:
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    barrier_hit: str  # 'profit_take', 'stop_loss', 'time_expiry'
    label: int        # 1 if profit_take, 0 otherwise


def get_triple_barriers(candles, events_indices, pt_points=150, sl_points=100, max_holding_bars=1440):
    """Applies horizontal profit-taking, horizontal stop-loss, and vertical time-limit barriers.

    Next-bar execution rule strictly observed.
    """
    out = []
    point_size = 0.01  # XAUUSD standard point
    for idx in events_indices:
        if idx >= len(candles) - 1:
            continue
        entry_candle = candles[idx + 1]  # Next-bar open
        entry_price = entry_candle.open
        pt_price = entry_price + pt_points * point_size
        sl_price = entry_price - sl_points * point_size

        hit = 'time_expiry'
        exit_idx = min(idx + 1 + max_holding_bars, len(candles) - 1)
        exit_price = candles[exit_idx].close
        label = 0

        for cur in range(idx + 1, exit_idx + 1):
            c = candles[cur]
            if c.high >= pt_price:
                hit = 'profit_take'
                exit_idx = cur
                exit_price = pt_price
                label = 1
                break
            if c.low <= sl_price:
                hit = 'stop_loss'
                exit_idx = cur
                exit_price = sl_price
                label = 0
                break

        out.append(BarrierEvent(idx + 1, exit_idx, entry_price, exit_price, hit, label))
    return out
