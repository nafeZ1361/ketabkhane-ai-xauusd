"""Constant-memory streaming backtest (same semantics as backtest.run_backtest)."""

from __future__ import annotations

from collections import deque

from .backtest import COST_LABEL_NO_COSTS, BacktestResult, Trade, compute_metrics


class _MovingAverage:
    """Identical arithmetic order to strategies.sma() so results match bit-for-bit."""

    def __init__(self, window):
        self.window = window
        self.values = deque()
        self.total = 0.0
        self.count = 0

    def push(self, value):
        self.values.append(value)
        self.count += 1
        self.total += value
        if self.count > self.window:
            self.total -= self.values.popleft()
        return self.total / self.window if self.count >= self.window else None


class StreamingBacktester:
    """Feed candles in order; signals execute at the next bar open."""

    def __init__(self, spec, profile=None, trend_window=None):
        self.spec = spec
        self.profile = profile
        self.trend_window = trend_window
        self.trend = _MovingAverage(trend_window) if trend_window else None
        self.fast = _MovingAverage(spec.fast)
        self.slow = _MovingAverage(spec.slow)
        self.prev_fast = None
        self.prev_slow = None
        self.pending = 0
        self.position = None
        self.index = -1
        self.last = None
        self.trades = []
        self.equity = [0.0]

    def _close_position(self, when, price, reason, index):
        entry_time, entry_price, entry_index = self.position
        pnl = self.profile.net_pnl(entry_price, price, entry_time, when) if self.profile else price - entry_price
        self.trades.append(Trade(entry_time, when, entry_price, price, round(pnl, 6),
                                 index - entry_index, reason))
        self.equity.append(round(self.equity[-1] + pnl, 6))
        self.position = None

    def feed(self, candle):
        self.index += 1
        if self.pending == 1 and self.position is None:
            self.position = (candle.time, candle.open, self.index)
        elif self.pending == -1 and self.position is not None:
            self._close_position(candle.time, candle.open, "signal", self.index)
        self.pending = 0

        fast = self.fast.push(candle.close)
        slow = self.slow.push(candle.close)
        trend_value = self.trend.push(candle.close) if self.trend else None
        if None not in (fast, slow, self.prev_fast, self.prev_slow):
            if self.prev_fast <= self.prev_slow and fast > slow:
                if trend_value is None or candle.close > trend_value:
                    self.pending = 1
            elif self.prev_fast >= self.prev_slow and fast < slow:
                self.pending = -1
        self.prev_fast, self.prev_slow = fast, slow
        self.last = candle

    def finish(self):
        if self.position is not None and self.last is not None:
            self._close_position(self.last.time, self.last.close, "end_of_data", self.index)
        result = BacktestResult(spec=self.spec, label=self.profile.label if self.profile else COST_LABEL_NO_COSTS,
                                trades=self.trades, equity=self.equity)
        result.metrics = compute_metrics(self.trades, self.equity)
        return result


def run_stream(candles, spec, profile=None, trend_window=None):
    engine = StreamingBacktester(spec, profile, trend_window)
    for candle in candles:
        engine.feed(candle)
    return engine.finish()