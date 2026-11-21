# 02 — ROADMAP AND GATES

Current authority: PROJECT_STATE.md, DECISIONS_LOG.md and the phase-specific approved plan. This file was reconciled on 2026-11-21; older S1–S7 notes below are retained only in Git history, not as current status.

## Accepted phases

| Phase | Status | Authority |
|---|---|---|
| 0–0.5 | DONE | PROJECT_STATE.md |
| 1 | PASS (provisional human sign-off status retained) | PROJECT_STATE.md |
| 2 | ACCEPTED under A-08; PHASE2-CLOCK-RECHECK-1 tracked separately | PROJECT_STATE.md / DECISIONS_LOG.md |
| 3 | ACCEPTED | D-022 |
| 4 Risk | ACCEPTED | D-024 |
| 4b Monte Carlo | ACCEPTED | D-027; S11 independent PASS |

## Phase 5 — Firewall

**Status: PRE-REGISTERED, BLOCKED ON D-008.** See PHASE5_PLAN.md and D-028. Frozen weights: F1 10, F2 12, F3 12, F4 15, F5 15, F6 15, F7 13, F8 8 (100 total). No F1–F8 implementation gate starts until every entry gate in PHASE5_PLAN.md is evidenced, especially hermetic/hash-verified D-008 closure. Redaction hardening and documentation reconciliation are prerequisite remediation, not Phase 5 gate acceptance.

Each gate requires focused positive/negative tests, mutation evidence where applicable, full suite, compileall, timestamped evidence + SHA-256 sidecar, and independent read-only Inspector PASS on a frozen snapshot. Developer self-approval is prohibited.

## Later phases

| Phase | Name | Status | Rule |
|---|---|---|---|
| 6 | Backtest | NOT STARTED | Separate pre-registered plan and owner approval required |
| 7 | Monitoring | NOT STARTED | Separate pre-registered plan and owner approval required |
| 8 | Integration | NOT STARTED | Separate pre-registered plan and owner approval required |
| 9 | Independent audit | NOT STARTED | Scope and criteria require approved plan |
| 10 | Remediation | NOT STARTED | Driven by Phase 9 findings and approved scope |
| 11 | DEMO readiness | NOT STARTED | A-05 plus separate explicit owner approval; no order submission authorized now |

Do not invent criteria or weights for Phases 6–11. No live execution test is required or authorized as part of the current development completion path.

## Standing safety constraints

- DEMO remains disabled; A-05 is absent. LIVE trading is unsupported and prohibited.
- A-04 is absent; do not read balance, equity, margin or profit.
- No order submission or request construction in Phase 5; no bypass or alternate execution route.
- No new dependency without written justification and owner approval.
- Never edit applied migrations or existing evidence; never weaken tests, rewrite history or force-push.
- D-019 remains DEFERRED. PHASE2-CLOCK-RECHECK-1 remains separately tracked; do not misreport it as closed without its required evidence.
