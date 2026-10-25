"""Bar-by-bar long-only backtester with next-bar execution."""

from __future__ import annotations

from dataclasses import dataclass, field

from .strategies import signals

COST_LABEL_NO_COSTS = "NO_TRADING_COSTS"


@dataclass(frozen=True)
class Trade:
    entry_time: object
    exit_time: object
    entry_price: float
    exit_price: float
    pnl: float
    bars: int
    reason: str


@dataclass
class BacktestResult:
    spec: object
    label: str
    trades: list = field(default_factory=list)
    equity: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def compute_metrics(trades, equity):
    n = len(trades)
    net = sum(t.pnl for t in trades)
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        max_dd = max(max_dd, peak - value)
    return {
        "trades": n,
        "net_pnl": round(net, 6),
        "win_rate": round(len(wins) / n, 6) if n else 0.0,
        "profit_factor": profit_factor,
        "max_drawdown": round(max_dd, 6),
    }


def run_backtest(candles, spec, profile=None, trend_window=None):
    """Long-only: signal on close, executed at the next bar open."""
    sig = signals(candles, spec, trend_window)
    trades = []
    equity = [0.0]
    entry_index = None
    entry_price = 0.0
    for i in range(len(candles) - 1):
        if sig[i] == 1 and entry_index is None:
            entry_index = i + 1
            entry_price = candles[i + 1].open
        elif sig[i] == -1 and entry_index is not None:
            exit_index = i + 1
            exit_price = candles[exit_index].open
            pnl = profile.net_pnl(entry_price, exit_price, candles[entry_index].time, candles[exit_index].time) if profile else exit_price - entry_price
            trades.append(Trade(candles[entry_index].time, candles[exit_index].time,
                                entry_price, exit_price, round(pnl, 6),
                                exit_index - entry_index, "signal"))
            equity.append(round(equity[-1] + pnl, 6))
            entry_index = None
    if entry_index is not None:
        exit_price = candles[-1].close
        pnl = profile.net_pnl(entry_price, exit_price, candles[entry_index].time, candles[-1].time) if profile else exit_price - entry_price
        trades.append(Trade(candles[entry_index].time, candles[-1].time,
                            entry_price, exit_price, round(pnl, 6),
                            len(candles) - 1 - entry_index, "end_of_data"))
        equity.append(round(equity[-1] + pnl, 6))
    result = BacktestResult(spec=spec, label=profile.label if profile else COST_LABEL_NO_COSTS,
                            trades=trades, equity=equity)
    result.metrics = compute_metrics(trades, equity)
    return result