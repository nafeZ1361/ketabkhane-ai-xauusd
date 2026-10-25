"""Stage 8: validation research layer over the frozen Stage 7 evidence runs.

Scope (stage7/GAPS.md GAP-005..GAP-007):
- GAP-005: Monte Carlo trade-sequence resampling of run1 holdout trades.
- GAP-006: Parameter landscape — re-run the identical Stage 7 pipeline across a
  pre-registered grid (cost, threshold, horizon) with fresh evidence dirs.
- GAP-007: Slippage/execution friction sensitivity (HIGH priority; executed via
  the GAP-006 cost axis).

Governance contract:
- Research-only. No live trading, no real orders, no MT5 execution in this layer.
- Frozen artifacts are read-only inputs: stage7/evidence/run1, run2, stage7_data/.
  Every Stage 8 output lands in a NEW directory and is hash-chained to the source
  run1 evidence it was derived from.
- Determinism: fixed seeds, stable sorts, float64 round(x, 10), no wall-clock
  values inside hashed artifacts (same policy as Stage 7 / F-002).
"""

STAGE8_VERSION = "stage8-v1"
