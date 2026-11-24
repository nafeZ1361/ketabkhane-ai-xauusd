# PHASE 12 — CONTROLLED DEMO EXECUTION VALIDATION

Status: PRE-REGISTERED / BLOCKED ON PHASE 11 AND ACCOUNT-DATA/RISK GATES (2026-11-23)
Authority: D-030 + append-only approval A-09. No execution is authorized before all prerequisites pass.
Prerequisite: Phase 11 accepted with independent read-only Inspector PASS.

## Mission

Run one bounded 4-hour-30-minute XAUUSD DEMO execution test after engineering completion. Guardian may autonomously open, manage, modify, and close its own DEMO positions during the approved window; no per-trade human approval is required. This is a validation exercise, not a profitability claim or production release.

## Hard boundary

- DEMO account only; LIVE and CONTEST modes are forbidden.
- Approved terminal path and server must match the owner-approved broker profile.
- Exact instrument: `XAUUSD.`; no symbol fallback.
- All order request construction, pre-checks and submission remain inside the independently isolated firewall process.
- The existing read-only MT5 adapter must remain read-only.
- No trade outside the test window; no continuation or restart after shutdown without a new authorization.
- No martingale, grid, averaging-down, unbounded stacking or risk escalation.
- Stop immediately on account-mode uncertainty, server/company mismatch, stale or invalid market data, clock uncertainty, spread breach, missing SL, risk drift, kill-switch failure, audit failure, IPC/authentication failure, or any unexpected execution response.
- The system must never fall back to LIVE, SIMULATED or a different account after a DEMO guard failure.

## Authorization and account-data prerequisites

1. Verify the existing append-only `approvals/A-09.json` against its record hash and previous A-08 hash. It authorizes autonomous trades only after Phase 11 PASS, for the exact duration, symbol, account mode and risk limits in the final test manifest. Do not rewrite historical approval records.
2. A-04 is still absent. Do not read balance, equity, margin or profit until A-04 is explicitly granted. Because the current Phase 4 sizing function requires equity, execution remains BLOCKED until either:
   - A-04 is explicitly granted for the minimum fields strictly required for sizing; or
   - a separately accepted, fixed-volume risk contract is implemented and proven not to require account financial fields.
3. Do not assume the meaning of the existing `0.25` risk setting. Resolve its unit and calculation path from code/config and freeze it in the test manifest before execution. Never increase it.
4. No credentials or account identifiers may be written to evidence or logs.

## Required engineering before this phase

- Phase 5 F1–F8 independently accepted; execution boundary and Kill Switch are proven.
- Phase 6 backtest and Phase 7 monitoring independently accepted.
- Phase 8 integration independently accepted.
- Phase 9 audit has no unresolved blocker; Phase 10 remediation accepted.
- Phase 11 DEMO readiness independently accepted.
- Resolve the current policy conflict: MetaTrader5 imports are confined to approved adapter code, while order-request construction and order submission are confined to the firewall process. Freeze one enforceable boundary and prove it with AST/negative tests before implementation.
- Do not add PyTorch to this validation path. The test evaluates the accepted deterministic Guardian strategy; Second Brain/ML remains a later shadow-only extension.

## Frozen test protocol

- Duration: exactly 4 hours 30 minutes from a recorded UTC start.
- One broker, one approved DEMO account, one exact symbol.
- Record each closed-bar signal, market snapshot, strategy version, risk decision, order request hash, broker retcode, fill, SL/TP, modification, closure, costs, slippage and latency.
- Use broker-native server time evidence plus UTC-normalized timestamps; do not infer clock offset from a fixed assumption.
- A signal is not an order authorization: every proposed trade must pass independent firewall validation of account, symbol, freshness, spread, stop distance, lot step, per-trade risk, aggregate exposure and kill-switch state.
- No parameter tuning or strategy changes during the test.
- If no valid signal occurs, record zero trades; do not force trades to make the test appear useful.
- At the end of the window, stop new entries and follow the pre-tested shutdown policy for test-owned positions. Do not silently leave positions unmanaged.

## Evaluation

Report signal precision/false positives, missed valid opportunities where measurable, realized and unrealized P&L, expectancy, win/loss distribution, maximum adverse/favourable excursion, drawdown, exposure, holding time, spread, commission, swap, slippage, latency, rejected requests, safety stops and reconciliation discrepancies. Separate strategy quality from execution quality. A 4h30m sample is operational evidence only; it cannot establish statistical profitability.

## Acceptance and evidence

- Full positive/negative, mutation, boundary and failure-injection tests.
- Exact commands, exit codes, environment fingerprint and frozen source revision.
- Hash-linked run manifest and append-only order/event ledger with secrets/account identifiers redacted.
- Broker history reconciled against Guardian events; every discrepancy explained.
- Independent read-only Inspector PASS on the frozen implementation and final test evidence.
- Verdict: PASS / FAIL / BLOCKED / INDEPENDENCE_NOT_ESTABLISHED.
- No developer self-approval.

## Prohibitions

No LIVE trading, no live-mode implementation, no credentials in repository, no force-push, no history rewrite, no destructive cleanup, no unapproved dependency, no per-trade risk increase, and no execution before all prerequisites pass.
