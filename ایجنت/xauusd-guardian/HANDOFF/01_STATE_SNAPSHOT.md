# 01 — CURRENT STATE SNAPSHOT

Snapshot baseline: 2026-11-21
Accepted baseline revision: 907f4e37ce63ce2b28a33cb5132d70831032a56e
Current work branch: work/guardian-risk-research-second-brain-audit

## Authoritative phase status

| Area | Status | Authority |
|---|---|---|
| Phase 1 | PASS (provisional sign-off) | PROJECT_STATE.md |
| Phase 2 | ACCEPTED under A-08 | PROJECT_STATE.md, A-08 |
| Phase 3 | ACCEPTED | D-022 |
| Phase 4 | ACCEPTED | D-024 |
| D-019 research test relocation | DEFERRED | D-019/D-021 |
| Phase 5 firewall/order path | NOT STARTED | A-05 not granted |
| Phase 2 clock recheck | Separate ticket OPEN/BLOCKED on 2026-11-21 attempt | D-025 |

Older status text in historical artifacts is not current authority. D-022/D-024 supersede earlier S7/Phase 4 blockers.

## Safety and approvals

- DEMO-only; no live trading, order construction or order submission.
- A-04 account Balance/Equity/Margin/Profit access: NOT REQUESTED. Use synthetic fixtures only.
- A-05 DEMO order checks/execution: NOT REQUESTED.
- D-019 remains DEFERRED.
- No applied migration or historical evidence may be edited.
- Current work is on a separate branch; do not merge to main without explicit approval.

## Known source gaps at this snapshot

1. src/guardian/domain/risk/sizing.py: max_lot clamp can return a value not divisible by lot_step. A regression correction is included in this work branch.
2. Handoff documents had stale Phase 3/4 statuses; current branch synchronizes their entry points without changing historic evidence.
3. Phase 4 is pure per-trade sizing only. Portfolio/daily loss limits, drawdown gate and emergency stop require a separate synthetic-input control layer; account integration remains forbidden.
4. scripts/research_edge.py is a single chronological holdout model comparison, not a realistic trade simulator, Monte Carlo engine or sequential walk-forward.
5. domain.market.quality already has bar/tick sanity checks; alert policy for stale tick and spread anomaly is a separate capability to verify/implement.
6. Second Brain is not an existing connected repository in the available repo inventory. Schema proposal is design-only.

## Evidence baseline

Phase 3: artifacts/phase3-closure-20261120T1255Z.md, D-022.
Phase 4: artifacts/phase4-inspection-20261121T1720Z.md, D-024.
Phase 2 clock recheck attempt: evidence/phase2-clock-recheck-20261121T171004Z.txt, D-025.
No new tests are claimed as executed by this snapshot. Consult current branch CI and independent inspection evidence for remediation status.
