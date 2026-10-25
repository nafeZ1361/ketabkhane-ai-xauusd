"""A3 breakout-family runner: pre-registered Donchian grid -> experiment ledger.

Satisfies A3_SCOPE constraint 4 (M >= 2 strategy FAMILIES): the MA family is
covered by scripts/a3_grid.py; this script registers a genuinely different
family — Donchian-channel breakout with next-bar-open execution, long-only.

Pre-registration (Charter v2.0 section 14 / docs/A3_SCOPE.md):
- the channel windows below are FIXED before any result is observed;
- every trial appends to artifacts/ledger/experiments.jsonl with
  is_retroactive=false and full reproducibility fields;
- validation/gates.yaml thresholds are NEVER touched here.

Usage:
    python scripts/a3_breakout.py --csv path/to/XAUUSD_M1.csv \
        [--profile config/broker_provisional.json]

Without a local dataset the script refuses to invent numbers and exits 2
(NO_EXEC_ENV honesty rule).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # validation package lives at repo root

from xauusd_research.backtest import COST_LABEL_NO_COSTS, BacktestResult, Trade, compute_metrics  # noqa: E402
from xauusd_research.costs import BrokerProfile  # noqa: E402
from xauusd_research.schema import iter_candles  # noqa: E402

from validation.ledger import Ledger  # noqa: E402
from validation.metrics import block_bootstrap_ci, sharpe_ratio  # noqa: E402

# --------------------------------------------------------------------------
# PRE-REGISTERED GRID — fixed list, do not edit after seeing results.
# family "breakout": Donchian entry window; exit = prior high of EXIT window.
ENTRY_WINDOWS = (20, 55)
EXIT_WINDOWS = (10,)
# A3_LEDGER_PATH lets tests redirect the ledger away from artifacts/.
LEDGER_PATH = Path(os.environ.get("A3_LEDGER_PATH") or
                  ROOT / "artifacts" / "ledger" / "experiments.jsonl")


def profit_factor_from(pnls):
    wins = sum(p for p in pnls if p > 0)
    losses = -sum(p for p in pnls if p < 0)
    if losses > 0:
        return wins / losses
    return float("inf") if wins > 0 else 0.0


class BreakoutBacktester:
    """Donchian breakout, long-only, next-bar-open execution.

    Signal semantics mirror the MA engines (a signal on bar i executes at the
    open of bar i+1). The channel is computed from CLOSED bars only: the bar
    that generates the breakout enters at the next open, never its own close.
    """

    def __init__(self, name, entry_window, exit_window, profile=None):
        self.name = name
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.profile = profile
        self.highs = deque(maxlen=entry_window)
        self.lows = deque(maxlen=exit_window)
        self.pending = 0
        self.position = None
        self.index = -1
        self.last = None
        self.trades = []
        self.equity = [0.0]

    def _close_position(self, when, price, reason, index):
        entry_time, entry_price, entry_index = self.position
        pnl = (self.profile.net_pnl(entry_price, price, entry_time, when)
               if self.profile else price - entry_price)
        self.trades.append(Trade(entry_time, when, entry_price, price,
                                 round(pnl, 6), index - entry_index, reason))
        self.equity.append(round(self.equity[-1] + pnl, 6))
        self.position = None

    def feed(self, candle):
        self.index += 1
        if self.pending == 1 and self.position is None:
            self.position = (candle.time, candle.open, self.index)
        elif self.pending == -1 and self.position is not None:
            self._close_position(candle.time, candle.open, "signal", self.index)
        self.pending = 0

        # Channel state BEFORE folding in the current bar (closed bars only).
        if len(self.highs) == self.entry_window and self.position is None:
            if candle.close > max(self.highs):
                self.pending = 1
        if len(self.lows) == self.exit_window and self.position is not None:
            if candle.close < min(self.lows):
                self.pending = -1

        self.highs.append(candle.high)
        self.lows.append(candle.low)
        self.last = candle

    def finish(self):
        if self.position is not None and self.last is not None:
            self._close_position(self.last.time, self.last.close,
                                 "end_of_data", self.index)
        label = self.profile.label if self.profile else COST_LABEL_NO_COSTS
        result = BacktestResult(spec=self.name, label=label,
                                trades=self.trades, equity=self.equity)
        result.metrics = compute_metrics(self.trades, self.equity)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, help="path to M1 CSV (local only)")
    parser.add_argument("--profile", default=None,
                        help="broker cost profile JSON (PROVISIONAL_COST_SCENARIO)")
    parser.add_argument("--limit", type=int, default=0,
                        help="run only first K grid cells (resume support)")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"dataset not found: {csv_path} — refusing to fabricate evidence",
              file=sys.stderr)
        return 2

    data_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    profile = BrokerProfile.load(args.profile) if args.profile else None
    if profile is None:
        print("no broker profile supplied: running with NO_TRADING_COSTS label; "
              "results cannot certify profitability", file=sys.stderr)

    ledger = Ledger(LEDGER_PATH)
    existing = {r.get("strategy") for r in ledger.records()
                if r.get("data_version_hash") == data_hash}

    combos = [(e, x) for e in ENTRY_WINDOWS for x in EXIT_WINDOWS]
    if args.limit:
        combos = combos[:args.limit]

    engines = {}
    rows = 0
    for candle in iter_candles(csv_path):
        rows += 1
        if not engines:
            for entry, exit_w in combos:
                name = f"donchian_{entry}_{exit_w}"
                engines[name] = BreakoutBacktester(name, entry, exit_w, profile)
        for engine in engines.values():
            engine.feed(candle)

    runs = 0
    for name, engine in sorted(engines.items()):
        if name in existing:
            continue
        result = engine.finish()
        trades = result.trades
        pnls = [t.pnl for t in trades]
        metrics = {"trades": len(trades)}
        if len(trades) >= 8:
            metrics["net_pnl"] = round(sum(pnls), 6)
            metrics["profit_factor"] = round(profit_factor_from(pnls), 6)
            metrics["sharpe"] = round(sharpe_ratio(pnls), 6)
            if len(trades) >= 60:
                ci = block_bootstrap_ci(pnls, profit_factor_from,
                                        block_size=60, samples=1000,
                                        seed=20261026)
                metrics["pf_lower_ci"] = round(ci["lower"], 6)
                metrics["pf_upper_ci"] = round(ci["upper"], 6)
        entry, exit_w = name.removeprefix("donchian_").split("_")
        record = ledger.append({
            "strategy": name,
            "family": "breakout",
            "trend_window": None,
            "phase": "A3-grid",
            "data_version_hash": data_hash,
            "cost_label": result.label,
            "metrics": metrics,
            "rows": rows,
            "is_retroactive": False,
            "params": {"entry_window": int(entry), "exit_window": int(exit_w)},
        })
        runs += 1
        print(f"seq={record['seq']:>3} {name:<18} "
              f"trades={metrics.get('trades', 0):>5} "
              f"net={metrics.get('net_pnl', 'n/a'):>12} "
              f"PF={metrics.get('profit_factor', 'n/a')}")

    report = ledger.verify()
    print(f"ledger records={report['records']} intact={report['intact']} "
          f"head={report['head_hash'][:12]}… new_runs={runs}")
    return 0 if report["intact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
