# Stage A — Baseline Audit (research harness)

Date: 2026-11-17 · Asia/Tehran 20:30 (UTC+03:30) · UTC 17:00
Repository: `nafeZ1361/ketabkhane-ai-xauusd` · branch `fix/w1-timezone-validation`
Starting HEAD: `c192c16c2df89f05327cc6512b728cb0ba9af134`
Working tree at start: clean. Scope touched by this stage: **none** (audit only).

## 1. Baseline tests (executed, unmodified)

```
python -m pytest -q --junitxml=out/stageA.xml
exit 0 · tests=302 · failures=0 · errors=0 · skipped=0
```

Includes `tests/unit/test_research_features.py` (2 tests: truncation invariance,
forward-label boundary).

## 2. What the pipeline actually does

`scripts/research_edge.py`:

| Step | Line | Behaviour |
|---|---|---|
| Load | 32-40 | MT5 TSV, `DATE`+`TIME` → timestamp, dedupe, sort, last `--bars` rows |
| Features | 43-66 | returns(1,5,15,60), EMA(20)/EMA(50) gap, RSI(14), ATR(14), 60-bar vol, hour, dow |
| Label | 69 | `close.shift(-horizon)/close - 1`, sign → binary |
| Split | 76 | chronological 70/30 at a single index |
| Models | 83-87 | logistic, depth-4 tree, HistGradientBoosting |
| Threshold | 90 | long if `p > 0.55` |
| Cost | 106 | flat `--cost 0.0002` |

Features are causal: every rolling/ewm term is trailing, and the truncation test
proves it. `StandardScaler` is fitted inside the pipeline, on training data only.

## 3. Defects found (severity, evidence)

**D1 — no purge/embargo at the split (critical, leakage).** Line 76 splits on index
alone. The last `horizon` training rows have labels built from prices *after* the
split, i.e. from the test period. With `horizon=15` and 209,947 training rows, 15
labels cross the boundary. The model is trained on information from the test set.

**D2 — horizon is counted in rows, not time (critical, correctness).** Line 69 uses
`shift(-horizon)`. XAUUSD M1 has weekend and holiday gaps; 15 rows is not reliably 15
minutes. The protocol forbids assuming a row count equals a duration. The true
elapsed time of each label is never measured or reported.

**D3 — the cost is invented (critical, cost).** Line 106 applies a flat 0.0002
"round-trip cost". The `spread` column *is* loaded (line 40) and then never used. No
commission, no slippage, no bid/ask distinction. Per the protocol this must be either
measured from the data or declared as an unsupported assumption — today it is
presented as if it were a measured cost.

**D4 — execution prices are not executable (critical, execution).** Entry is assumed
at the close of the signal bar and exit at the close `horizon` bars later. The close
of the signal bar is already known when the signal is produced, so it cannot be the
fill; no spread crossing, no next-bar open, no quote side. Long-only (line 90); the
short side is never evaluated.

**D5 — overlapping labels treated as independent (high, statistics).** Consecutive
bars share 14 of 15 forward-return bars (and 59 of 60). Any AUC confidence interval
or per-trade mean computed as if `n = 2,174` is overstated by roughly `horizon`.
No dependence correction is applied.

**D6 — the test set was used for selection (high, validity).** Three model families
and two horizons were run, and the best was highlighted; threshold 0.55 is hardcoded
and was never chosen on a validation fold. This is test-set selection.

**D9 — the "always-long" reference is mislabelled and misused (high, benchmark).**
The reference printed at line 100 is `test["fwd"].mean()`: the mean of *overlapping*
forward returns over every test bar. That is not buy-and-hold (which is the compounded
return from the first to the last price) and it is not a tradeable strategy. D-018
turned it into "always-long is negative after cost", which compares an average of
overlapping windows to a per-trade cost. Both the label and the sentence must be
withdrawn; a true buy-and-hold comparison has to be computed separately.

**D10 — a single holdout is called "walk-forward" (medium, terminology).**
The module docstring, the D-018 entry and the commit subject say walk-forward. The
code makes one chronological 70/30 split with no re-fitting. That is a single holdout;
calling it walk-forward overstates the validation design and must be corrected in all
three places (the commit subject is historical and cannot be rewritten).

**D7 — data-integrity guards are absent (medium).** No NaN/Inf price check, no
duplicate-timestamp policy beyond "keep first", no gap awareness: rolling windows
silently span weekend holes.

**D8 — "signals" are reported as if they were trades (medium, reporting).** Overlapping
signals are counted separately; the report gives per-trade means without stating that
the same forward window is reused.

## 4. What is sound and must be preserved

- Feature causality, proven by `test_truncation_does_not_change_past_features`.
- Chronological (not shuffled) split.
- Scaler fitted on train only, inside the pipeline.
- Deterministic seeds; identical inputs give identical output.

## 5. Proposed minimal changes for the next stages

| Stage | Change |
|---|---|
| B | Purge the last `horizon` training rows; add embargo; define horizon by timestamp with `searchsorted` on the time index (not row count); report elapsed-time distribution; exclude incomplete labels explicitly. |
| C | Derive cost from the `spread` column (points → price → return), state commission as an explicit assumption or mark `BLOCKED`; enter at next bar open ± half-spread; separate gross and net; apply each cost once. |
| D | Block bootstrap by trading day (overlap-aware); report CI for AUC and mean net; no threshold change without a training-only procedure; declare all prior test-set exposure. |
| E | Tests for purge/embargo, horizon-in-time, entry-after-signal, exit-after-entry, cost-once, gross/net equality, overlap handling, fail-closed on NaN/Inf, determinism. |

## 6. Position on the existing result

The recorded `D-018` numbers are **not reproducible as evidence of an edge** until D1
and D3 are corrected, and its reference-line sentence is withdrawn (D9): one is leakage and the other is an invented cost. The negative
conclusion is likely to survive, but it is currently supported by a flawed harness.

## 7. Stage status

Stage A: **complete, independently PASSed** (see REPORT-STAGE-A-2).
Working-tree delta at the end of Stage A: two files modified (`research_edge.py` docstring/label,`DECISIONS_LOG.md` correction bullet) plus this untracked audit. No commit, no push, no data deletion.
