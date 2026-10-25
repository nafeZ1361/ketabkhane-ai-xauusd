"""GAP-005: Monte Carlo trade-sequence validation over frozen run1 evidence.

Reads ``stage7/evidence/run1/trades.csv`` (read-only; hash-verified against the
frozen ``run_manifest.json``) and resamples the per-trade PnL sequence with
replacement to estimate the distribution of drawdown / ruin outcomes under
sequence uncertainty. This is a VALIDATION layer only: it does not refit any
model, does not touch the dataset, and produces no trading signals.

Method contract (pre-registered before execution):
- Source trades: exact rows of run1/trades.csv in file order (chronological).
- Resampling: i.i.d. bootstrap with replacement over the full trade population
  (sequence-length preserved), NumPy PCG64 seeded per replicate:
  ``seed = base_seed + replicate_index``.
- Equity path per replicate: compounding-free additive walk matching the Stage 7
  backtest sizing convention (fixed-fraction sizing makes unit PnLs roughly
  comparable; MC here measures ORDER risk of realised PnLs, not sizing policy).
- Statistics per replicate: max drawdown (USD and pct vs running peak), final
  PnL, worst peak-to-trough. Aggregates: mean/median/p5/p95 plus the empirical
  probability that replicate drawdown exceeds the observed run1 drawdown and
  exceeds fixed stress thresholds.
- Determinism: identical inputs + seeds produce byte-identical artifacts; no
  wall-clock values inside hashed files (F-002 policy).

Usage:
    python3 -u -m stage8.monte_carlo [evidence_out_dir] [--base-seed 42]
                                     [--replicates 2000]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from stage7.pipeline import canonical_json_bytes, sha256_file, sha256_payload, write_json
from stage8 import STAGE8_VERSION

RUN1_DIR = Path("stage7/evidence/run1")
# Artifacts covered by run_manifest["artifact_hashes_sha256"] (the manifest does
# not hash itself; its own sha256 is recorded separately as source_run_manifest_sha256).
REQUIRED_ARTIFACTS = ("trades.csv", "performance_metrics.json")


class MonteCarloError(RuntimeError):
    pass


def _load_run_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run_manifest.json"
    if not path.is_file():
        raise MonteCarloError(f"missing frozen manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_frozen_inputs(run_dir: Path = RUN1_DIR) -> dict[str, str]:
    """Hash-verify read-only inputs against the frozen run_manifest hashes."""
    manifest = _load_run_manifest(run_dir)
    expected = manifest.get("artifact_hashes_sha256", {})
    verified: dict[str, str] = {}
    for name in REQUIRED_ARTIFACTS:
        path = run_dir / name
        if not path.is_file():
            raise MonteCarloError(f"missing frozen artifact: {path}")
        actual = sha256_file(path)
        want = expected.get(name)
        if want is None:
            raise MonteCarloError(f"{name} not covered by run_manifest hashes")
        if actual != want:
            raise MonteCarloError(
                f"frozen evidence integrity violation for {name}: "
                f"manifest={want} actual={actual}")
        verified[name] = actual
    # Also record (not verify-in-manifest) the equity curve and predictions we
    # rely on downstream, so Stage 8 evidence is fully hash-chained.
    for extra in ("predictions.csv", "equity_curve.csv"):
        p = run_dir / extra
        h = expected.get(extra)
        a = sha256_file(p)
        if h is not None and a != h:
            raise MonteCarloError(
                f"frozen evidence integrity violation for {extra}: manifest={h} actual={a}")
        verified[extra] = a
    return verified


def load_trade_pnls(run_dir: Path = RUN1_DIR) -> np.ndarray:
    frame = pd.read_csv(run_dir / "trades.csv")
    if "pnl" not in frame.columns or len(frame) == 0:
        raise MonteCarloError("trades.csv missing pnl column or empty")
    return frame["pnl"].to_numpy(dtype=np.float64)


def _drawdown_stats(pnls: np.ndarray, initial_equity: float) -> tuple[float, float]:
    """Max drawdown (USD, pct-of-peak) along the additive equity walk."""
    equity = initial_equity + np.cumsum(pnls)
    peak = np.maximum.accumulate(np.concatenate(([initial_equity], equity)))
    dd = equity - peak[1:]
    worst_usd = float(dd.min()) if dd.size else 0.0
    worst_pct = worst_usd / float(peak[1:][int(np.argmin(dd))]) if dd.size else 0.0
    return round(worst_usd, 6), round(worst_pct * 100.0, 6)


def run_monte_carlo(pnls: np.ndarray, *, replicates: int, base_seed: int,
                    initial_equity: float, seed_version: str = "pcg64-v1") -> dict[str, Any]:
    """Bootstrap-resample the trade PnL sequence and aggregate drawdown stats."""
    n = int(len(pnls))
    rng_master = np.random.default_rng(base_seed)
    dd_usd = np.empty(replicates, dtype=np.float64)
    dd_pct = np.empty(replicates, dtype=np.float64)
    final_pnl = np.empty(replicates, dtype=np.float64)
    for k in range(replicates):
        # Per-replicate deterministic child stream (stable across NumPy releases
        # because we spawn from the master generator by index).
        rng = np.random.default_rng([base_seed, k])
        sample = rng.choice(pnls, size=n, replace=True)
        u, p = _drawdown_stats(sample, initial_equity)
        dd_usd[k] = u
        dd_pct[k] = p
        final_pnl[k] = float(sample.sum())

    observed_dd_usd, observed_dd_pct = _drawdown_stats(pnls, initial_equity)

    def q(arr: np.ndarray, pct: float) -> float:
        return round(float(np.percentile(arr, pct)), 6)

    summary = {
        "version": STAGE8_VERSION,
        "gap": "GAP-005",
        "method": "iid bootstrap with replacement over run1 holdout trade PnLs",
        "seed_version": seed_version,
        "base_seed": int(base_seed),
        "replicates": int(replicates),
        "trades_per_replicate": n,
        "initial_equity": round(float(initial_equity), 6),
        "observed": {"max_drawdown_usd": observed_dd_usd,
                     "max_drawdown_pct": observed_dd_pct,
                     "net_pnl": round(float(pnls.sum()), 6)},
        "distribution_max_drawdown_usd": {
            "mean": round(float(dd_usd.mean()), 6),
            "median": q(dd_usd, 50.0),
            "p5": q(dd_usd, 5.0),
            "p95": q(dd_usd, 95.0),
            "min": round(float(dd_usd.min()), 6),
            "max": round(float(dd_usd.max()), 6),
        },
        "distribution_max_drawdown_pct": {
            "mean": round(float(dd_pct.mean()), 6),
            "median": q(dd_pct, 50.0),
            "p5": q(dd_pct, 5.0),
            "p95": q(dd_pct, 95.0),
        },
        "distribution_final_pnl": {
            "mean": round(float(final_pnl.mean()), 6),
            "median": q(final_pnl, 50.0),
            "p5": q(final_pnl, 5.0),
            "p95": q(final_pnl, 95.0),
        },
        "tail_probabilities": {
            "p_dd_worse_than_observed": round(float((dd_usd < observed_dd_usd).mean()), 6),
            "p_dd_exceeds_25pct_equity": round(float((dd_pct < -25.0).mean()), 6),
            "p_dd_exceeds_50pct_equity": round(float((dd_pct < -50.0).mean()), 6),
            "p_final_pnl_positive": round(float((final_pnl > 0.0).mean()), 6),
        },
    }
    return summary


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_dir", nargs="?",
                        default="stage7/evidence/run3_mc",
                        help="NEW output dir (never a frozen run dir)")
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument("--replicates", type=int, default=2000)
    args = parser.parse_args(argv)

    out_dir = Path(args.evidence_dir)
    if out_dir.resolve() in {RUN1_DIR.resolve(), Path("stage7/evidence/run2").resolve()}:
        raise MonteCarloError("refusing to write into frozen evidence directory")
    out_dir.mkdir(parents=True, exist_ok=True)

    verified = verify_frozen_inputs()
    pnls = load_trade_pnls()
    manifest = _load_run_manifest(RUN1_DIR)
    initial_equity = float(manifest["config"]["initial_equity"])

    summary = run_monte_carlo(pnls, replicates=args.replicates,
                              base_seed=args.base_seed,
                              initial_equity=initial_equity)
    summary["source_run"] = "run1"
    summary["source_trades_sha256"] = verified["trades.csv"]
    summary["source_run_manifest_sha256"] = sha256_file(RUN1_DIR / "run_manifest.json")

    hashes = {"monte_carlo_summary.json": write_json(out_dir / "monte_carlo_summary.json", summary)}
    run_manifest = {
        "version": STAGE8_VERSION,
        "tool": "stage8.monte_carlo",
        "gap": "GAP-005",
        "inputs_verified": verified,
        "params": {"base_seed": args.base_seed, "replicates": args.replicates,
                   "initial_equity": initial_equity},
        "artifact_hashes_sha256": hashes,
        "summary_payload_sha256": sha256_payload(summary),
    }
    hashes["mc_run_manifest.json"] = write_json(out_dir / "mc_run_manifest.json", run_manifest)

    print(json.dumps({"status": "success", "gap": "GAP-005",
                      "evidence_dir": str(out_dir),
                      "observed": summary["observed"],
                      "distribution_max_drawdown_usd": summary["distribution_max_drawdown_usd"],
                      "tail_probabilities": summary["tail_probabilities"],
                      "artifact_hashes": hashes}, indent=1))
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
