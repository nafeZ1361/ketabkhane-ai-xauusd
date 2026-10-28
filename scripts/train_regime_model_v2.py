"""Train the v2 regime model (sequence features + triple-barrier labels).

Usage:
    python scripts/train_regime_model_v2.py XAUUSD._M1_....csv \
        --out models/regime_v2 [--stride 5] [--no-dnn] [--k-up 1.0 --k-down 1.0]

Exit code 0 only when training completes; ``beats_baseline`` is recorded in
metrics.json but does NOT change the exit code — declaring a model tradable
remains a human decision (governance rule).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xauusd_research.ml_engine.trainer_v2 import TrainConfigV2, train_model_v2
from xauusd_research.schema import load_candles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="MT5-style candles CSV/TSV")
    parser.add_argument("--out", type=Path, default=Path("models/regime_v2"))
    parser.add_argument("--name", default="regime_v2")
    parser.add_argument("--stride", type=int, default=5)
    parser.add_argument("--k-up", dest="k_up", type=float, default=1.0)
    parser.add_argument("--k-down", dest="k_down", type=float, default=1.0)
    parser.add_argument("--no-dnn", dest="train_dnn", action="store_false")
    args = parser.parse_args(argv)

    print(f"[train-v2] loading candles from {args.csv} ...", flush=True)
    candles = load_candles(args.csv)
    print(f"[train-v2] loaded {len(candles)} candles", flush=True)

    cfg = TrainConfigV2(
        name=args.name,
        stride=args.stride,
        k_up=args.k_up,
        k_down=args.k_down,
        train_dnn=args.train_dnn,
    )
    metrics = train_model_v2(candles, args.csv, args.out, cfg)
    print(json.dumps({
        "samples": metrics["samples"],
        "label_counts": metrics["label_counts"],
        "rf_final_eval": metrics["rf_final_eval"],
        "dnn_final_eval": metrics["dnn_final_eval"],
        "dnn_holdout": metrics["dnn_holdout"],
    }, indent=2))
    rf_beat = metrics["rf_final_eval"]["beats_baseline"]
    dnn_beat = bool(metrics["dnn_final_eval"] and
                    metrics["dnn_final_eval"]["beats_baseline"])
    print(f"[train-v2] artifacts written to {args.out}")
    print(f"[train-v2] rf_beats_baseline={rf_beat} dnn_beats_baseline={dnn_beat} "
          f"-> {'CANDIDATE' if (rf_beat or dnn_beat) else 'NOT-TRADABLE (honest FAIL)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
