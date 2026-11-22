# PHASE 7 — MONITORING

Status: PRE-REGISTERED / WAITING FOR PHASE 6 ACCEPTANCE (2026-11-22)
Authority: D-029. Implementation starts only after Phase 6 independent acceptance.

## Mission
Build read-only operational monitoring for data quality, signal health, risk-contract health, process liveness and safety-boundary violations. Monitoring must fail closed on unknown/invalid states and must not expose secrets or account financial fields.

## Frozen acceptance criteria
1. Every monitored metric has an explicit source, type, unit and validity rule.
2. Stale, missing, malformed or contradictory telemetry produces a deterministic degraded/blocked state; never a false healthy state.
3. Alerts are deduplicated and deterministic; timestamps use one documented clock authority.
4. Logs/metrics cannot expose credentials, account identifiers, tokens, or prohibited financial fields; redaction is mandatory.
5. Monitoring cannot enable DEMO/LIVE, construct orders, or call broker order/account APIs.
6. Health status is independently reproducible from recorded inputs.
7. Failure injection covers stale data, process death, malformed telemetry, disk/storage faults and redaction bypass.
8. Full suite + compileall + evidence + SHA-256 sidecars pass.
9. Independent read-only Inspector PASS on a frozen snapshot is required.

## Safety
No LIVE/DEMO activation, no order construction/submission, no account financial-field access, no destructive cleanup, no new dependency without approval.

## Deliverables
Monitoring domain/service, read-only CLI/report, alert contract, tests, failure-injection evidence, state/decision updates, independent inspection package.
