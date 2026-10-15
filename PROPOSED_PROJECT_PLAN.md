# XAUUSD ML Research — Proposed Project Plan

**Status: Draft; Stage 0 BLOCKED**  
**Priority:** correctness, safety, leakage prevention, reproducibility, validation, evidence quality, documentation.

## Stage sequence
1. **Stage 0 — Scope and provenance:** establish data origin, permissions, symbol/time conventions, repository boundaries, and acceptance evidence. No model or trading execution.
2. **Stage 1 — Data audit:** validate schema, timestamps, duplicates, gaps, OHLC integrity, and immutable input hashes.
3. **Stage 2 — Features and target:** define features and target horizons; test for look-ahead and leakage.
4. **Stage 3 — Baseline model:** establish a reproducible baseline and fixed evaluation protocol.
5. **Stage 4 — Signal and execution assumptions:** specify rules and costs without sending real orders.
6. **Stage 5 — Backtest:** deterministic, cost-aware historical simulation.
7. **Stage 6 — Robustness and statistical validation:** time-aware splits, purge/embargo where applicable, sensitivity checks, and leakage tests.
8. **Stage 7 — Evidence and reproducibility:** manifests, hashes, logs, and repeatable validation.
9. **Stage 8 — Paper validation and final audit:** simulated/paper-only validation and independent review; no live trading.

## Mandatory stage gate
For every stage: AUDIT → RCA → MINIMAL FIX → TEST → VALIDATE → EVIDENCE → PASS/BLOCKED → HUMAN CONFIRMATION → NEXT STAGE.

## Mandatory rollback/recovery capability
Before Stage 1 implementation begins, design and test the project-wide checkpoint and rollback mechanism in `ROLLBACK_AND_RECOVERY.md`. Every stage must start from a recorded last-known-good checkpoint and either create a new accepted checkpoint or remain BLOCKED. On failure, preserve logs and evidence, restore only through a traceable recovery commit/branch, verify code/config/data hashes and tests, and require human approval for protected actions. Never delete evidence, mutate source data, rewrite shared history, use force-push, or silently downgrade the baseline. This is a required design/test gate, not yet an implemented feature.

No stage advances on assumptions. UNKNOWN, INCOMPLETE, or FAIL is not PASS. Applicable scope, test, validation, reproducibility, evidence, integrity, safety, and governance checks must be reviewed before approval.

## Frozen safety limits
- Research/backtest/paper validation only; not live trading.
- No real orders, broker credentials, autonomous trading, or production deployment.
- No merge/push or protected-scope action without explicit human approval.
- No silent baseline, data, evidence, or test changes.
- Keep governance changes separate from code changes.
- Prefer small, simple, import-safe, testable code.

## Current authorized work
Stage 0 audit and planning documentation only. The old backtest folder has been inventoried and statically reviewed, but no files are approved for reuse. No Stage 1 work is authorized by this plan.
