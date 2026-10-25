"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .backtest import run_backtest
from .costs import BrokerProfile
from .report import write_manifest, write_summary, write_trades
from .schema import SchemaError, iter_candles, load_candles
from .strategies import STRATEGY_BY_NAME
from .stream import StreamingBacktester
from .timezones import POLICIES
from .validation import StreamingValidator, validate

STREAM_THRESHOLD_BYTES = 64 * 1024 * 1024


def build_parser():
    parser = argparse.ArgumentParser(prog="xauusd-research", description="MVP-1 research pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="validate data, run strategy, write trades")
    run.add_argument("--csv", required=True, help="input CSV/TSV path")
    run.add_argument("--out", required=True, help="output directory")
    run.add_argument("--strategy", default="ma_5_20", choices=sorted(STRATEGY_BY_NAME))
    run.add_argument("--server-tz", default="eu-dst", choices=list(POLICIES),
                     help="broker server timezone policy (default: eu-dst for Europe/Kyiv)")
    run.add_argument("--mode", default="auto", choices=["auto", "stream", "memory"],
                     help="auto streams files larger than 64 MB")
    run.add_argument("--broker-profile", default=None,
                     help="JSON broker profile; enables cost-aware results")
    run.add_argument("--trend-window", type=int, default=None,
                     help="optional long-term trend filter window")
    return parser


def run_pipeline(csv_path, out_dir, strategy_name, server_tz="eu-dst", mode="auto", broker_profile=None,
                 trend_window=None):
    started = time.perf_counter()
    path = Path(csv_path)
    if not path.is_file():
        raise SchemaError(f"input file not found: {path}")
    streaming = mode == "stream" or (mode == "auto" and path.stat().st_size > STREAM_THRESHOLD_BYTES)
    profile = BrokerProfile.load(broker_profile) if broker_profile else None
    spec = STRATEGY_BY_NAME[strategy_name]

    if streaming:
        engine = StreamingBacktester(spec, profile, trend_window)
        validator = StreamingValidator()
        for candle in iter_candles(path, server_tz):
            validator.feed(candle)
            engine.feed(candle)
        report = validator.report()
        result = engine.finish() if not report.fatal else None
    else:
        candles = load_candles(path, tz_policy=server_tz)
        report = validate(candles)
        result = None if report.fatal else run_backtest(candles, spec, profile, trend_window)

    if report.fatal:
        return 2, {"status": "INVALID_DATA", "issues": [i.code for i in report.issues]}

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    trades_path = write_trades(result, out / "trades.csv")
    summary_path = write_summary(result, report, out / "summary.json", input_path=path,
                                 server_tz=server_tz, profile=profile.describe() if profile else None)
    manifest_path = write_manifest([path], [trades_path, summary_path], out / "manifest.json")
    return 0, {
        "status": "OK",
        "mode": "stream" if streaming else "memory",
        "strategy": spec.name,
        "server_tz": server_tz,
        "cost_label": result.label,
        "broker_profile": profile.profile_id if profile else None,
        "trend_window": trend_window,
        "metrics": result.metrics,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "trades_csv": str(trades_path),
        "manifest": str(manifest_path),
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        code, payload = run_pipeline(args.csv, args.out, args.strategy, args.server_tz,
                                     args.mode, args.broker_profile, args.trend_window)
    except SchemaError as exc:
        print(f"schema error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"broker profile error: {exc}", file=sys.stderr)
        return 3
    print(payload.get("status"))
    if code == 0:
        print(f"mode: {payload['mode']}  costs: {payload['cost_label']}  "
              f"trades: {payload['metrics']['trades']}  net_pnl: {payload['metrics']['net_pnl']}  "
              f"elapsed: {payload['elapsed_seconds']}s")
    return code