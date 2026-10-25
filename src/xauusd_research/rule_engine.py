"""Deterministic rule-engine backtester (R1): AST signals + next-bar execution.

Governing docs: Charter v2.0 section 14, ADL-006/ADL-007, blueprint layer 4
("must be deterministic and fast"). Reuses the frozen cost model (ADL-004)
and the same Trade/metrics contract as backtest.py so results are directly
comparable with the legacy MA engine.

Causality guarantees (AT-R1-causality):
- Signal is evaluated on bar i CLOSE only using bars <= i.
- Entry/exit executes at bar i+1 OPEN (next-bar, no look-ahead).
- SL/TP intrabar checks use bar extremes but resolve pessimistically:
  if both could trigger within one bar, stop-loss wins.
"""

from __future__ import annotations

from .backtest import Trade, compute_metrics, BacktestResult
from .rule_ast import Compare, Const, Ind, Logic, Price
from .strategies import sma


class RuleEngineError(ValueError):
    """Raised when evaluation cannot proceed (warmup, unknown node)."""


# ---------------------------------------------------------------------------
# Indicator series (precomputed once per run, strictly causal windows)
# ---------------------------------------------------------------------------

def ema(values, window):
    if window <= 0:
        raise RuleEngineError("ema window must be positive")
    out = [None] * len(values)
    k = 2.0 / (window + 1)
    acc = None
    for i, value in enumerate(values):
        acc = value if acc is None else value * k + acc * (1 - k)
        if i >= window - 1:
            out[i] = acc
    return out


def rsi(closes, window):
    if window < 2:
        raise RuleEngineError("rsi window must be >= 2")
    out = [None] * len(closes)
    gains = losses = 0.0
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        g, l = max(change, 0.0), max(-change, 0.0)
        if i <= window:
            gains += g
            losses += l
            if i == window:
                ag, al = gains / window, losses / window
                out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)
        else:
            ag = (ag * (window - 1) + g) / window
            al = (al * (window - 1) + l) / window
            out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)
    return out


def atr(candles, window):
    if window < 1:
        raise RuleEngineError("atr window must be >= 1")
    trs = []
    for i, c in enumerate(candles):
        if i == 0:
            trs.append(c.high - c.low)
        else:
            pc = candles[i - 1].close
            trs.append(max(c.high - c.low, abs(c.high - pc), abs(c.low - pc)))
    out = [None] * len(candles)
    acc = None
    for i, tr in enumerate(trs):
        acc = tr if acc is None else (acc * (window - 1) + tr) / window
        if i >= window - 1:
            out[i] = acc
    return out


def donchian_high(candles, window):
    out = [None] * len(candles)
    for i in range(window - 1, len(candles)):
        out[i] = max(c.high for c in candles[i - window + 1:i + 1])
    return out


def donchian_low(candles, window):
    out = [None] * len(candles)
    for i in range(window - 1, len(candles)):
        out[i] = min(c.low for c in candles[i - window + 1:i + 1])
    return out


def build_series(candles, needs):
    """Materialize every indicator series required by a strategy once."""
    closes = [c.close for c in candles]
    series = {}
    for spec in needs:
        key = (spec["kind"], spec["window"])
        if key in series:
            continue
        kind, w = key
        if kind == "sma":
            series[key] = sma(closes, w)
        elif kind == "ema":
            series[key] = ema(closes, w)
        elif kind == "rsi":
            series[key] = rsi(closes, w)
        elif kind == "atr":
            series[key] = atr(candles, w)
        elif kind == "donchian":
            series[("donchian_h", w)] = donchian_high(candles, w)
            series[("donchian_l", w)] = donchian_low(candles, w)
        else:
            raise RuleEngineError(f"unhandled indicator: {kind}")
    return series


def _value(node, i, candles, series):
    if isinstance(node, Const):
        return node.value
    j = i - getattr(node, "offset", 0)
    if j < 0:
        return None
    if isinstance(node, Price):
        return getattr(candles[j], node.field)
    if isinstance(node, Ind):
        if node.kind == "donchian":
            # Donchian is directional; callers compare price vs channel via
            # explicit rhs nodes — default to the high channel here.
            got = series.get(("donchian_h", node.window))
        else:
            got = series.get((node.kind, node.window))
        return None if got is None else got[j]
    raise RuleEngineError(f"unknown value node: {type(node).__name__}")


def eval_bool(node, i, candles, series):
    """Evaluate a boolean node at bar i. None (warmup) => False."""
    if isinstance(node, Compare):
        lhs = _value(node.lhs, i, candles, series)
        rhs = _value(node.rhs, i, candles, series)
        if lhs is None or rhs is None:
            return False
        if node.op == ">":
            return lhs > rhs
        if node.op == "<":
            return lhs < rhs
        if node.op == ">=":
            return lhs >= rhs
        return lhs <= rhs
    if isinstance(node, Logic):
        if node.op == "and":
            return all(eval_bool(c, i, candles, series) for c in node.children)
        if node.op == "or":
            return any(eval_bool(c, i, candles, series) for c in node.children)
        return not eval_bool(node.children[0], i, candles, series)
    raise RuleEngineError(f"unknown boolean node: {type(node).__name__}")


# ---------------------------------------------------------------------------
# Signal arrays
# ---------------------------------------------------------------------------

def rule_signals(candles, strategy):
    """+1/-1/0 per bar from entry trees (evaluated on close of bar i)."""
    series = build_series(candles, strategy.indicator_needs())
    n = len(candles)
    out = [0] * n
    want_long = strategy.direction in ("long", "both")
    want_short = strategy.direction in ("short", "both")
    for i in range(n):
        if want_long and eval_bool(strategy.long_entry, i, candles, series):
            out[i] = 1
        elif want_short and strategy.short_entry is not None \
                and eval_bool(strategy.short_entry, i, candles, series):
            out[i] = -1
    return out


# ---------------------------------------------------------------------------
# Backtest loop (single position, long/short, next-bar fills, SL/TP)
# ---------------------------------------------------------------------------

def run_rule_backtest(candles, strategy, profile=None):
    """Long/short rule backtest reusing the frozen cost model.

    PnL sign follows position direction; costs (spread+slippage+commission
    +swap) are deducted symmetrically via profile.net_pnl for longs and a
    mirrored computation for shorts.
    """
    if not candles:
        raise RuleEngineError("no candles")
    sig = rule_signals(candles, strategy)
    ex = strategy.exit_rule
    trades = []
    equity = [0.0]
    pos_dir = 0          # +1 long, -1 short, 0 flat
    entry_index = None
    entry_price = 0.0

    def net(direction, ep, xp, et, xt):
        if profile is None:
            return round((xp - ep) * direction, 6)
        base = profile.net_pnl(ep, xp, et, xt) if direction > 0 else None
        if base is not None:
            return base
        # Mirror: short pnl flips gross, keeps costs identical.
        gross = (ep - xp) * profile.contract_size * profile.lots
        nights = 0
        if et is not None and xt is not None:
            nights = max((xt.date() - et.date()).days, 0)
        return round(gross - profile.cost_per_trade()
                     - profile.swap_cost(ep, nights), 6)

    for i in range(len(candles) - 1):
        bar_next = candles[i + 1]
        # Manage open position with exits first (pessimistic order).
        if pos_dir != 0:
            held = i + 1 - entry_index
            exit_px = None
            reason = None
            if ex.stop_loss_pct is not None:
                sl = entry_price * (1 - ex.stop_loss_pct) if pos_dir > 0 \
                    else entry_price * (1 + ex.stop_loss_pct)
                tp = None
                if ex.take_profit_pct is not None:
                    tp = entry_price * (1 + ex.take_profit_pct) if pos_dir > 0 \
                        else entry_price * (1 - ex.take_profit_pct)
                hit_sl = bar_next.low <= sl if pos_dir > 0 else bar_next.high >= sl
                hit_tp = (tp is not None) and (
                    bar_next.high >= tp if pos_dir > 0 else bar_next.low <= tp)
                if hit_sl:                      # stop-loss wins ties
                    exit_px, reason = sl, "stop_loss"
                elif hit_tp:
                    exit_px, reason = tp, "take_profit"
            elif ex.take_profit_pct is not None:
                tp = entry_price * (1 + ex.take_profit_pct) if pos_dir > 0 \
                    else entry_price * (1 - ex.take_profit_pct)
                if bar_next.high >= tp if pos_dir > 0 else bar_next.low <= tp:
                    exit_px, reason = tp, "take_profit"
            if exit_px is None and ex.max_bars is not None and held >= ex.max_bars:
                exit_px, reason = bar_next.open, "max_bars"
            if exit_px is not None:
                pnl = net(pos_dir, entry_price, exit_px,
                          candles[entry_index].time, bar_next.time)
                trades.append(Trade(candles[entry_index].time, bar_next.time,
                                    entry_price, exit_px, round(pnl, 6),
                                    held, reason))
                equity.append(round(equity[-1] + pnl, 6))
                pos_dir = 0
                entry_index = None
                continue
        # New signal on close of bar i -> fill at open of bar i+1.
        if sig[i] != 0 and pos_dir == 0:
            pos_dir = sig[i]
            entry_index = i + 1
            entry_price = bar_next.open
    if pos_dir != 0 and entry_index is not None:
        exit_px = candles[-1].close
        pnl = net(pos_dir, entry_price, exit_px,
                  candles[entry_index].time, candles[-1].time)
        trades.append(Trade(candles[entry_index].time, candles[-1].time,
                            entry_price, exit_px, round(pnl, 6),
                            len(candles) - 1 - entry_index, "end_of_data"))
        equity.append(round(equity[-1] + pnl, 6))
    result = BacktestResult(spec=strategy, label=(profile.label if profile else "NO_TRADING_COSTS"),
                            trades=trades, equity=equity)
    result.metrics = compute_metrics(trades, equity)
    return result
