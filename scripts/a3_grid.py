"""A3 grid runner: pre-registered MA parameter grid -> experiment ledger.

Pre-registration (Charter v2.0 section 14 / docs/A3_SCOPE.md):
- the grid below is FIXED before any result is observed;
- every trial is appended to `artifacts/ledger/experiments.jsonl` with
  ``is_retroactive=false`` and full reproducibility fields;
- thresholds in validation/gates.yaml are NEVER touched here.

Usage:
    python scripts/a3_grid.py --csv path/to/XAUUSD_M1.csv \
        [--profile config/broker_provisional.json] [--limit K]

Without a local dataset (CSV lives outside Git) the script refuses to invent
numbers and exits with a clear message (NO_EXEC_ENV honesty rule).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # validation package lives at repo root

from xauusd_research.costs import BrokerProfile  # noqa: E402
from xauusd_research.schema import iter_candles  # noqa: E402
from xauusd_research.strategies import StrategySpec  # noqa: E402
from xauusd_research.stream import StreamingBacktester  # noqa: E402

from validation.ledger import Ledger  # noqa: E402
from validation.metrics import block_bootstrap_ci, sharpe_ratio  # noqa: E402

# --------------------------------------------------------------------------
# PRE-REGISTERED GRID — fixed list, do not edit after seeing results.
# family "ma": fast/slow crossover; trend filter 500 as registered in A3.
GRID_FAST = (5, 10, 20, 50, 100)
GRID_SLOW = (20, 50, 100, 200, 400)
TREND_WINDOWS = (None, 500)
# A3_LEDGER_PATH lets tests redirect the ledger away from artifacts/.
LEDGER_PATH = Path(os.environ.get("A3_LEDGER_PATH") or
                  ROOT / "artifacts" / "ledger" / "experiments.jsonl")


def build_grid() -> list[tuple]:
    combos = []
    for fast in GRID_FAST:
        for slow in GRID_SLOW:
            if fast >= slow:
                continue
            for trend in TREND_WINDOWS:
                combos.append((fast, slow, trend))
    return combos


def profit_factor(trades):
    gross_win = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = -sum(t.pnl for t in trades if t.pnl < 0)
    if gross_loss > 0:
        return gross_win / gross_loss
    return float("inf") if gross_win > 0 else 0.0


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
    existing = {(r.get("strategy"), r.get("trend_window"))
                for r in ledger.records() if r.get("data_version_hash") == data_hash}

    grid = build_grid()
    if args.limit:
        grid = grid[:args.limit]

    engines = {}
    rows = 0
    for candle in iter_candles(csv_path):
        rows += 1
        if not engines:
            for fast, slow, trend in grid:
                spec = StrategySpec(f"ma_{fast}_{slow}", fast, slow)
                engines[(fast, slow, trend)] = (spec, StreamingBacktester(spec, profile, trend))
        for _spec, engine in engines.values():
            engine.feed(candle)

    runs = 0
    for (fast, slow, trend), (spec, engine) in sorted(engines.items(), key=lambda kv: str(kv[0])):
        name = spec.name
        if (name, trend) in existing:
            continue
        result = engine.finish()
        trades = result.trades
        pnls = [t.pnl for t in trades]
        metrics = {"trades": len(trades)}
        if len(trades) >= 8:
            metrics["net_pnl"] = round(sum(pnls), 6)
            metrics["profit_factor"] = round(profit_factor(trades), 6)
            metrics["sharpe"] = round(sharpe_ratio(pnls), 6)
            if len(trades) >= 60:
                ci = block_bootstrap_ci(pnls, lambda xs: profit_factor_from(xs),
                                        block_size=60, samples=1000, seed=20261026)
                metrics["pf_lower_ci"] = round(ci["lower"], 6)
                metrics["pf_upper_ci"] = round(ci["upper"], 6)
        record = ledger.append({
            "strategy": name,
            "family": "ma",
            "trend_window": trend,
            "phase": "A3-grid",
            "data_version_hash": data_hash,
            "cost_label": result.label,
            "metrics": metrics,
            "rows": rows,
            "is_retroactive": False,
        })
        runs += 1
        print(f"seq={record['seq']:>3} {name:<12} trend={trend!s:<5} "
              f"trades={metrics.get('trades', 0):>5} "
              f"net={metrics.get('net_pnl', 'n/a'):>12} "
              f"PF={metrics.get('profit_factor', 'n/a')}")

    report = ledger.verify()
    print(f"ledger records={report['records']} intact={report['intact']} "
          f"head={report['head_hash'][:12]}… new_runs={runs}")
    return 0 if report["intact"] else 1


def profit_factor_from(pnls):
    wins = sum(p for p in pnls if p > 0)
    losses = -sum(p for p in pnls if p < 0)
    if losses > 0:
        return wins / losses
    return float("inf") if wins > 0 else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
