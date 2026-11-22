# PHASE 6 — BACKTEST

Status: PRE-REGISTERED / WAITING FOR PHASE 5 ACCEPTANCE (2026-11-22)
Authority: D-029. Implementation starts only after Phase 5 independent acceptance.

## Mission
Build a deterministic, research-only backtest layer using accepted market-data, signal, and risk contracts. It must never place orders, construct broker requests, access account financial fields, or enable LIVE/DEMO execution.

## Scope
- Historical closed-bar input only; quarantined/invalid data excluded fail-closed.
- Reuse accepted Phase 3 signal contracts and Phase 4 risk sizing; do not duplicate their rules.
- Deterministic simulated entries/exits with explicit execution timing.
- Explicit spread/slippage/fee assumptions; no hidden costs.
- Position sizing from the approved risk contract; no account/broker reads.
- Trade ledger, equity curve, drawdown, return, win/loss, exposure and risk metrics.
- Reproducible JSON/Markdown report containing inputs, assumptions, seed if applicable, data digest, software revision and artifact hashes.
- Boundary and adversarial tests for look-ahead, forming bars, missing/duplicate data, invalid costs, invalid risk inputs, and nondeterminism.

## Acceptance criteria — frozen before implementation
1. No look-ahead: a decision at bar t can consume only information available by the declared decision timestamp.
2. Forming bars are rejected; closed-bar identity is explicit.
3. Determinism: identical inputs/spec/revision produce identical ledger and report digest.
4. Data integrity: missing, duplicate, reversed or quarantined input fails closed rather than being silently repaired.
5. Execution assumptions are explicit and reproducible; cost stress can be varied without hidden state.
6. Risk sizing delegates to the accepted Phase 4 contract and refuses invalid/non-finite/incorrect numeric types.
7. No trading surface: no MetaTrader5, account, order_send, order_check, broker request construction or LIVE/DEMO activation.
8. Metrics are mathematically consistent with the trade/equity ledger and include enough intermediate data to audit results.
9. Regression/adversarial/mutation tests prove critical guards fail when intentionally broken.
10. Full suite + compileall pass with exact commands, exit codes, timestamped evidence and SHA-256 sidecars.
11. Independent read-only Inspector PASS on a frozen snapshot is required for acceptance.

## Safety
- No broker connectivity required for Phase 6.
- No new dependency without written justification and owner approval.
- No parameter optimization, ML training, or strategy discovery in this phase.
- No changes to accepted migrations 0001–0003.
- No destructive data operations or evidence rewriting.

## Deliverables
- Backtest domain/service implementation.
- CLI/reporting entry point.
- Focused unit/security/regression tests.
- Reproducible evidence package.
- Updated PROJECT_STATE.md and DECISIONS_LOG.md.
- Independent inspection package and PASS record.

## Out of scope
Live verification, DEMO execution, broker order submission, optimization, ML, monitoring, integration deployment, and later-phase remediation.
