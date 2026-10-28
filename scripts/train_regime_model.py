"""Train the regime ML model on a server CSV and persist the artifact bundle.

Usage:
    python scripts/train_regime_model.py XAUUSD._M1_....csv --out models/regime_rf_v1

Writes evidence JSON (metrics + manifest) next to the model and prints a
compact summary. Exit code 0 only when training completes; the honesty flag
``final_eval_beats_baseline`` is printed but does NOT change the exit code —
declaring the model tradable remains a human decision (governance rule).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xauusd_research.ml_engine.trainer import TrainConfig, train_model
from xauusd_research.schema import load_candles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="MT5-style candles CSV/TSV")
    parser.add_argument("--out", type=Path, default=Path("models/regime_rf_v1"))
    parser.add_argument("--stride", type=int, default=10)
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--max-depth", type=int, default=8)
    args = parser.parse_args(argv)

    print(f"[train] loading candles from {args.csv} ...", flush=True)
    candles = load_candles(args.csv)
    print(f"[train] loaded {len(candles)} candles", flush=True)

    cfg = TrainConfig(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        stride=args.stride,
    )
    metrics = train_model(candles, args.csv, args.out, cfg)
    print(json.dumps(metrics, indent=2))
    print(f"[train] artifacts written to {args.out}")
    print(f"[train] final_eval_accuracy={metrics['final_eval_accuracy']} "
          f"beats_baseline={metrics['final_eval_beats_baseline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
