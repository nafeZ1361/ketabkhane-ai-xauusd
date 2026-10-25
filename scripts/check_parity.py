"""Compare the batch and streaming engines on the same file (evidence tool)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xauusd_research.backtest import run_backtest  # noqa: E402
from xauusd_research.schema import iter_candles, load_candles  # noqa: E402
from xauusd_research.strategies import STRATEGY_BY_NAME  # noqa: E402
from xauusd_research.stream import run_stream  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--strategy", default="ma_5_20")
    args = ap.parse_args()
    spec = STRATEGY_BY_NAME[args.strategy]

    batch = run_backtest(load_candles(args.csv), spec)
    streamed = run_stream(iter_candles(args.csv), spec)

    same_count = len(batch.trades) == len(streamed.trades)
    same_metrics = batch.metrics == streamed.metrics
    same_trades = all((a.entry_time, a.exit_time, a.pnl) == (b.entry_time, b.exit_time, b.pnl)
                      for a, b in zip(batch.trades, streamed.trades))
    print("strategy", args.strategy)
    print("batch_trades", len(batch.trades), "stream_trades", len(streamed.trades))
    print("same_count", same_count, "same_metrics", same_metrics, "same_trades", same_trades)
    print("PARITY", "PASS" if (same_count and same_metrics and same_trades) else "FAIL")
    return 0 if (same_count and same_metrics and same_trades) else 1


if __name__ == "__main__":
    raise SystemExit(main())