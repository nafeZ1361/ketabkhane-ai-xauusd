# PHASE 5 — FIREWALL

Status: **PRE-REGISTERED / BLOCKED ON D-008** (2026-11-21)
Decision: D-028. Weights are frozen before implementation.

## Mission
Build a fail-closed, isolated firewall boundary for a future DEMO-only execution capability. This phase does not authorize DEMO activation, broker order submission, or any live-trading path.

## Frozen deliverables and weights

| Gate | Deliverable | Weight |
|---|---|---:|
| F1 | Typed firewall contracts; strict schema/version validation | 10 |
| F2 | Central fail-closed policy and authorization checks | 12 |
| F3 | Independent risk revalidation at the boundary | 12 |
| F4 | Restricted worker process and authenticated, replay-resistant IPC | 15 |
| F5 | Persistent, fail-safe Kill Switch and recovery semantics | 15 |
| F6 | Disabled execution boundary; no order construction/submission in this phase | 15 |
| F7 | Mandatory redaction and tamper-evident audit trail | 13 |
| F8 | Adversarial, mutation, regression and full-suite verification | 8 |
| **Total** | | **100** |

Completion is weighted accepted work / 100. A gate earns weight only after independent inspection PASS. In-progress, failed, blocked or unverified work earns zero.

## Entry gates (all required)
1. Phase 4 and 4b acceptance records verified against their cited independent evidence (D-024, D-027).
2. D-008 closed with a hermetic Python 3.11 environment, pinned transitive dependencies and verified package hashes; no system-site-packages; reproducible offline installation from a documented wheelhouse or equivalent immutable source; full suite and preflight evidence.
3. Owner-approved scope and this frozen plan recorded in D-028.
4. Redaction cannot be disabled by API or config; negative tests cover both paths.
5. Scope and authority of nested AGENTS.md files are unambiguous.

Until every entry gate is proven, Phase 5 implementation gates F1–F8 remain NOT STARTED. No workaround or inherited system package may be treated as closing D-008.

## Security and scope constraints
- DEMO remains disabled; A-05 is absent. Activation requires A-05 plus separate explicit owner authorization.
- No LIVE mode, live flag, override, broker order submission, order request construction, order_send, or order_check in this phase.
- No account balance/equity/margin/profit access; A-04 remains absent.
- No new dependency without written justification and owner approval.
- No destructive data operation, applied-migration edit, evidence rewrite, force-push, or history rewrite.
- Preserve the accepted Phases 1–4b; changes require explicit regression evidence.
- Any order-related API, if ever separately authorized in a later phase, must remain isolated; this plan does not authorize implementing it.

## Per-gate acceptance
Each F1–F8 requires: implementation matching this plan; focused positive and negative tests; mutation/negative-control evidence where applicable; full suite + compileall with exact commands and exit codes; timestamped evidence and SHA-256 sidecar; updated state/decision records; independent read-only Inspector PASS on a frozen snapshot. Developer self-approval is prohibited. If inspector independence cannot be established, verdict is INDEPENDENCE_NOT_ESTABLISHED.

## Adversarial coverage
Unauthorized and malformed requests; unknown fields/versions; replayed, duplicated, stale, forged and unauthenticated IPC; risk drift; worker crash/restart; Kill Switch bypass and persistence failure; audit tampering; redaction bypass through API/config/nested data; attempts to reach any order API or LIVE mode. All must fail closed.

## Deferred / out of scope
Phase 6–11 detailed criteria are not invented here and require their own pre-registered plans. PHASE2-CLOCK-RECHECK-1 and D-019 remain separately tracked. No live execution test is part of project completion.
