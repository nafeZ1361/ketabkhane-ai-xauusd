# 02 — AUTHORIZED WORKSTREAMS AND ACCEPTANCE GATES

Owner instruction (2026-11-21): implement repository corrections, risk controls, realistic research/backtesting, Monte Carlo, walk-forward, regime analysis, kill switch, monitoring, Second Brain schema design, Claude skill extraction, tests and inspection.

This authorization does NOT grant account-data access (A-04), order checks/execution (A-05), live trading, new runtime dependencies, or permission to lock/implement Second Brain Layer 1.

## Workstreams

| ID | Workstream | Scope | Required gate |
|---|---|---|---|
| W0 | Repository integrity | Correct confirmed defects; synchronize handoff docs; append decision/evidence | Regression tests + Windows CI + independent review |
| W1 | Risk controls | Pure Decimal limits: per-trade sizing, daily/weekly loss, equity-curve drawdown, aggregate open risk, loss streak; synthetic/caller-supplied values | Fail-closed matrix, grid tests, no account/order imports |
| W2 | Event-driven backtest | Closed-bar signal at t executes no earlier than next bar; explicit spread, slippage, commission, stop/target and gap fills; deterministic trade ledger | Hand-calculated fixtures, no-lookahead, adverse intrabar ordering, costs tests |
| W3 | Robustness | Trade-sequence Monte Carlo; max drawdown distribution; chronological walk-forward folds with purge/embargo; no tuning on test folds | Seeded deterministic tests, leakage tests, out-of-sample separation |
| W4 | Market regimes | Closed-bar-only trend/range/volatility labels using past-only windows | Warmup, boundary, no-lookahead and deterministic tests |
| W5 | Kill switch + monitoring | Pure stop policy; stale tick, spread outlier, connection transition alerts; no order execution | Fail-closed state matrix and alert tests; read-only integration |
| W6 | Second Brain design | Proposed schema, provenance, append-only learning lifecycle, verified lesson promotion; Guardian connector read-only | Schema review and threat model; no Layer 1 until exact قفل Schema v0.1 |
| W7 | Claude skills | Inspect actual SKILL.md files at pinned commits; extract procedures into scoped checklists | Source hash, license, adversarial tests, independent review before approval |
| W8 | Final audit | Full suite, security boundary, reproducibility, evidence manifest, separate read-only Inspector | PASS or INDEPENDENCE_NOT_ESTABLISHED; never self-approve |

## Implementation constraints

- Preserve Phase 1–4 acceptance records. Newly found defects are separate post-acceptance findings with their own regression and review.
- No order path, account access, live mode, broker credentials or execution automation.
- No new dependency in Guardian runtime without separate written approval. Prefer stdlib.
- Keep the research ML experiment isolated; do not add pandas/scikit-learn to requirements.lock.
- Reuse existing market-quality logic; do not duplicate it.
- No database migration unless durable-storage need is proven and separately reviewed.
- Every engine exposes pure deterministic functions first. MT5 adapter remains read-only.

## Sequence

W0 → W1 → W2 → W3 → W4 → W5 → W6 design review → W7 extraction → W8.
A workstream advances only after focused tests and independent PASS on its frozen snapshot. Parallel design is allowed; shared-file edits are not.

## Completion definition

Required files and tests exist; full Windows CI passes; compileall passes; evidence hashes reproduce; no safety boundary regression; independent Inspector proves read-only identity and snapshot integrity; owner receives a concise report. Green CI is not independent acceptance.
