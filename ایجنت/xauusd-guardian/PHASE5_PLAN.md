# PHASE 5 — FIREWALL

Status: **PRE-REGISTERED / ENTRY READY — ALL FIVE ENTRY GATES INDEPENDENTLY VERIFIED** (2026-11-23)
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

> Gate 2 status (2026-11-23): AP-7 independent PASS recorded (report `47a9e1f6...`); hermetic Python 3.11.8, pinned hashes, offline install, 377/0/0 and compileall are verified. Current D-008 preflight evidence (`preflight-20261123T194424Z.json`, SHA-256 `1d80668eeb25b3c9e08c55c87391eb2e3e6707ec82a9141f3e0ac066d50a72bc`) passed 9/9 checks. Independent GuardianInspector review returned PASS (`REVIEW-REPORT.md`, SHA-256 `ced929a1...b9f2`; result `fa07fc49...5d5d`). Gate 2 is MET.

All five Phase 5 entry gates are now independently verified. Phase 5 implementation gates F1–F8 remain NOT STARTED and earn zero completion weight until each is implemented, tested and independently accepted. No workaround or inherited system package may be treated as closing D-008.

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

## F1 external Inspector evidence intake (2026-11-24)

An owner-supplied report body states `PASS` for inspection ID `PHASE5-F1-INSPECTION-e48729c` on target commit `e48729cbd92df86b63d3941d67fdcb8635210bf9`. The report's declared SHA-256 is `f8b8ae53f70b1112fa36d5b2c822ffcd433ad0d86ee105891b3485e2d2d29854`.

The evidence intake is registered at `evidence/external-inspector/PHASE5-F1-INSPECTION-e48729c-REGISTRATION.md`. This is a transcription/registration of information supplied in chat, **not the original report file**. Original report bytes and detached sidecar were unavailable; therefore the declared digest has not been recomputed. Raw `review-result.json`, pytest logs, compileall log, harness output and manifest files were not available for independent verification. Inspector identity and snapshot immutability are recorded as report claims, not re-executed by this registration.

GitHub Actions on the claimed exact target were checked: PR workflow runs `45452649612` and `45452649554` both report SUCCESS. These runs corroborate CI status only and do not authenticate the external Inspector report.

**Disposition:** F1 remains **INDEPENDENT ACCEPTANCE PENDING / 0 of 10** until an independent Inspector reviews this registration and determines whether the evidence-integrity limitations satisfy the acceptance policy. F2-F8 remain NOT STARTED; Phase 5 remains 0/100. No acceptance criteria are waived.


## F1 independent Inspector method addendum — D-033 (2026-11-26)

The owner approved replacing the local Windows GuardianInspector account/session procedure for F1 with the isolated GitHub Actions method in PHASE5_F1_GITHUB_INSPECTOR_PLAN.md. This supersedes the local SID/session/NTFS-ACL execution mechanism for F1 only; it does not waive independent inspection or any F1 contract/test/evidence requirement.

The Inspector must run on a separate ephemeral Windows runner from the freeze job, consume the exact source archive artifact after SHA-256 verification, use the separately pinned harness commit, run from a distinct writable copy, verify the hash-locked wheelhouse and offline install, execute focused/full tests and compileall, run black-box/static/mutation checks, and upload raw evidence with recomputable hashes.

The hosted runner is not claimed to be a separate human reviewer, a distinct local Windows SID, or proof of NTFS ACLs. No repository secrets or write token may be passed to target code. F1 remains 0/10 until one exact-run artifact is inspected and every acceptance condition in the new plan is verified. F2-F8 remain NOT STARTED.
