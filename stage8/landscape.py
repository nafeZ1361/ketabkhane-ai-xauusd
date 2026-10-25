"""GAP-006 / GAP-007: pre-registered parameter landscape with friction sensitivity.

Re-runs the EXACT Stage 7 pipeline (stage7.pipeline.run_pipeline — no reimplementation,
no modification of frozen Stage 7 code) across a small, pre-registered grid and
writes each variant into a NEW evidence directory. The axes:

- spread_cost_usd  : [0.00, 0.20, 0.30 (=run1), 0.50]   -> GAP-007 friction axis
                     (0.30 must reproduce run1 byte-for-byte; that reproduction is
                     itself the integrity gate for this tool.)
- entry_threshold  : [0.50 (=run1), 0.55, 0.60]         -> signal-confidence axis
- horizon          : [5 (=run1)]                        -> held fixed in v1 to keep
                     the grid auditable; feature/target recomputation per horizon
                     is deferred until the edge question is settled.

Implementation note on thresholds: ``run_pipeline`` hard-codes p>=0.5 signalization.
To avoid touching frozen Stage 7 logic, this module monkey-patches ONLY the local
comparison inside a wrapper by post-processing: it calls run_pipeline once per cost
value with threshold 0.5, then for higher thresholds re-derives trades from the
already-written predictions.csv + raw bars using the identical execution formula
(enter open[i+lag], exit open[i+lag+horizon], fixed-fraction sizing). Both paths
are covered by tests/test_stage8_landscape.py against the run1 reference.

Usage:
    python3 -u -m stage8.landscape <output_root_dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stage7.config import Stage7Config
from stage7.pipeline import (sha256_file, sha256_payload, write_json,
                             max_drawdown_stats, run_pipeline)
from stage8 import STAGE8_VERSION
from stage8.monte_carlo import verify_frozen_inputs, RUN1_DIR

# Pre-registered grid (fixed before execution; do not tune post-hoc).
COST_GRID_USD = (0.00, 0.20, 0.30, 0.50)
THRESHOLD_GRID = (0.50, 0.55, 0.60)
BASELINE_COST = 0.30      # == run1 contract value
BASELINE_THRESHOLD = 0.50


class LandscapeError(RuntimeError):
    pass


def _variant_config(cost: float, base: dict[str, Any]) -> Stage7Config:
    params = dict(base)
    params.pop("version", None)
    params["spread_cost_usd"] = float(cost)
    return Stage7Config(**params)


def _metrics_from_predictions(pred_csv: Path, opens: np.ndarray, holdout_idx: np.ndarray,
                              frame_timestamps: pd.Series, cost: float, threshold: float,
                              config: Stage7Config) -> dict[str, Any]:
    """Re-execute trades from frozen-style predictions at a given cost/threshold.

    Mirrors stage7.pipeline.run_backtest exactly (same sizing, lag, exit rule),
    but with configurable entry threshold and round-trip cost.
    """
    preds = pd.read_csv(pred_csv)
    probabilities = preds["probability"].to_numpy(dtype=np.float64)
    n = len(probabilities)
    lag, horizon = config.decision_lag, config.horizon
    equity = config.initial_equity
    curve: list[dict[str, Any]] = []
    trade_pnls: list[float] = []
    timestamps = frame_timestamps.to_numpy()
    for i in range(n):
        if probabilities[i] >= threshold:
            entry_i, exit_i = i + lag, i + lag + horizon
            if exit_i < n:
                entry = opens[entry_i]
                exit_price = opens[exit_i]
                units = max(equity * config.position_fraction / entry, 0.0)
                gross = units * (exit_price - entry)
                pnl = gross - cost * units
                equity += pnl
                trade_pnls.append(round(pnl, 6))
        curve.append({"equity": round(equity, 6)})
    dd = max_drawdown_stats(curve, config.initial_equity)
    wins = sum(1 for p in trade_pnls if p > 0)
    losses = sum(1 for p in trade_pnls if p < 0)
    gp = sum(p for p in trade_pnls if p > 0)
    gl = abs(sum(p for p in trade_pnls if p < 0))
    net = round(sum(trade_pnls), 6)
    return {
        "cost_usd": round(float(cost), 6),
        "threshold": round(float(threshold), 6),
        "signals_long": int((probabilities >= threshold).sum()),
        "trades": len(trade_pnls),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wins / len(trade_pnls) * 100.0, 6) if trade_pnls else 0.0,
        "profit_factor": round(gp / gl, 6) if gl else None,
        "net_pnl": net,
        "final_equity": round(equity, 6),
        "total_return_pct": round(net / config.initial_equity * 100.0, 6),
        **dd,
    }


def main(argv: list[str] | None = None) -> dict[str, Any]:
    out_root = Path(argv[0] if argv else "stage7/evidence/run3_landscape")
    if out_root.resolve() in {RUN1_DIR.resolve(),
                              Path("stage7/evidence/run2").resolve()}:
        raise LandscapeError("refusing to write into frozen evidence directory")

    # Integrity gate: frozen inputs must still hash-match before we derive anything.
    verified = verify_frozen_inputs()
    run1_manifest = json.loads((RUN1_DIR / "run_manifest.json").read_text(encoding="utf-8"))
    base_cfg_dict = dict(run1_manifest["config"])
    base_cfg_dict.pop("version", None)

    # --- Reproduction check: baseline cell must equal run1 metrics exactly -----
    # peak_memory_mb is machine-dependent by design (F-002); all other metric
    # fields must match the frozen run1 evidence bit-for-bit.
    repro_dir = out_root / "_repro_baseline"
    repro_summary = run_pipeline(_variant_config(BASELINE_COST, base_cfg_dict),
                                 repro_dir, "run3_repro")
    run1_metrics = json.loads((RUN1_DIR / "performance_metrics.json").read_text(encoding="utf-8"))
    repro_metrics = json.loads((repro_dir / "performance_metrics.json").read_text(encoding="utf-8"))
    key_fields = sorted(set(run1_metrics) - {"peak_memory_mb", "run_id"})
    mismatched = {f: (run1_metrics.get(f), repro_metrics.get(f))
                  for f in key_fields if run1_metrics.get(f) != repro_metrics.get(f)}
    if mismatched:
        raise LandscapeError(f"baseline reproduction FAILED vs frozen run1: {mismatched}")

    # --- Grid -------------------------------------------------------------------
    # Load raw bars once for re-execution at other costs/thresholds.
    from stage7.pipeline import load_dataset_streaming
    frame, _ = load_dataset_streaming(Path(base_cfg_dict["dataset_path"]),
                                      base_cfg_dict["chunk_rows"],
                                      expected_rows=base_cfg_dict["expected_rows"])
    labels_ok = pd.read_csv(RUN1_DIR / "predictions.csv")["index"].to_numpy()
    holdout_idx = labels_ok
    opens_all = frame["open"].to_numpy(dtype=np.float64)
    holdout_opens = opens_all[holdout_idx]
    holdout_ts = frame["timestamp"].iloc[holdout_idx].reset_index(drop=True)

    cells: list[dict[str, Any]] = []
    for cost in COST_GRID_USD:
        for thr in THRESHOLD_GRID:
            m = _metrics_from_predictions(repro_dir / "predictions.csv", holdout_opens,
                                          holdout_idx, holdout_ts, cost, thr,
                                          _variant_config(cost, base_cfg_dict))
            m["cell"] = f"cost{cost:.2f}_thr{thr:.2f}"
            m["is_baseline"] = (cost == BASELINE_COST and thr == BASELINE_THRESHOLD)
            cells.append(m)

    summary = {
        "version": STAGE8_VERSION,
        "gaps": ["GAP-006", "GAP-007"],
        "method": "exact Stage 7 re-execution + threshold/cost re-simulation on "
                  "frozen-baseline predictions; baseline cell byte-reproduces run1",
        "grid": {"spread_cost_usd": list(COST_GRID_USD),
                 "entry_threshold": list(THRESHOLD_GRID),
                 "horizon": [int(base_cfg_dict["horizon"])]},
        "baseline_reproduction": {"status": "PASS",
                                  "fields_checked": list(key_fields),
                                  "run1_trades_sha256": verified["trades.csv"]},
        "cells": cells,
    }
    hashes = {}
    hashes["landscape_summary.json"] = write_json(out_root / "landscape_summary.json", summary)
    manifest = {
        "version": STAGE8_VERSION,
        "tool": "stage8.landscape",
        "gaps": ["GAP-006", "GAP-007"],
        "inputs_verified": verified,
        "artifact_hashes_sha256": hashes,
        "summary_payload_sha256": sha256_payload(summary),
    }
    hashes["landscape_run_manifest.json"] = write_json(
        out_root / "landscape_run_manifest.json", manifest)

    print(json.dumps({"status": "success", "baseline_reproduction": "PASS",
                      "cells": [{k: c[k] for k in ("cell", "net_pnl", "max_drawdown_pct",
                                                   "profit_factor", "trades")}
                                for c in cells],
                      "artifact_hashes": hashes}, indent=1))
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
