# PHASE 8 — INTEGRATION

Status: PRE-REGISTERED / WAITING FOR PHASE 7 ACCEPTANCE (2026-11-22)
Authority: D-029. Implementation starts only after Phase 7 independent acceptance.

## Mission
Integrate accepted Guardian components through explicit contracts and fail-closed orchestration without enabling broker execution.

## Frozen acceptance criteria
1. Component boundaries are explicit and dependency direction remains valid.
2. Startup rejects incompatible schema/config/contract versions and unknown fields.
3. One deterministic end-to-end research/readiness flow succeeds from controlled fixtures.
4. Any component failure propagates to a safe blocked state; no partial success is reported as healthy.
5. Retry/restart behavior is idempotent and cannot duplicate persisted evidence or simulated trades.
6. Configuration and environment provenance are recorded in the run manifest.
7. No order request construction/submission, LIVE mode, DEMO activation, or prohibited account access.
8. Adversarial integration tests cover malformed messages, stale state, duplicate/replay input, component crash and dependency mismatch.
9. Full suite + compileall + evidence + SHA-256 sidecars pass.
10. Independent read-only Inspector PASS on a frozen snapshot is required.

## Safety
No destructive migration edits, force-push, evidence rewriting or new dependency without approval.
