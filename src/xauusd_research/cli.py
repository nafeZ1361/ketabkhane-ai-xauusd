"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .backtest import run_backtest
from .report import write_manifest, write_summary, write_trades
from .schema import SchemaError, load_candles
from .strategies import STRATEGY_BY_NAME
from .validation import validate


def build_parser():
    parser = argparse.ArgumentParser(prog="xauusd-research", description="MVP-1 research pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="validate CSV, run strategy, write trades")
    run.add_argument("--csv", required=True, help="input CSV path")
    run.add_argument("--out", required=True, help="output directory")
    run.add_argument("--strategy", default="ma_5_20", choices=sorted(STRATEGY_BY_NAME))
    return parser


def run_pipeline(csv_path, out_dir, strategy_name):
    candles = load_candles(csv_path)
    report = validate(candles)
    if report.fatal:
        return 2, {"status": "INVALID_DATA", "issues": [i.code for i in report.issues]}
    spec = STRATEGY_BY_NAME[strategy_name]
    result = run_backtest(candles, spec)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    trades_path = write_trades(result, out / "trades.csv")
    summary_path = write_summary(result, report, out / "summary.json", input_path=csv_path)
    manifest_path = write_manifest([csv_path], [trades_path, summary_path], out / "manifest.json")
    return 0, {
        "status": "OK",
        "strategy": spec.name,
        "cost_label": result.label,
        "metrics": result.metrics,
        "trades_csv": str(trades_path),
        "manifest": str(manifest_path),
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        code, payload = run_pipeline(args.csv, args.out, args.strategy)
    except SchemaError as exc:
        print(f"schema error: {exc}", file=sys.stderr)
        return 2
    print(payload.get("status"))
    if code == 0:
        print(f"trades: {payload['metrics']['trades']}  net_pnl: {payload['metrics']['net_pnl']}")
    return code