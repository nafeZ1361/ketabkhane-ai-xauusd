# PROJECT COMPLETION PLAN — XAUUSD GUARDIAN

Status: OWNER-DIRECTED EXECUTION PLAN (2026-11-22)
Authority: D-029 + phase-specific plans.

## Objective
Complete all engineering, safety, testing, audit, and readiness work without requiring a live-trading execution test. Live verification is a post-completion validation performed by the owner and reviewed from returned evidence.

## Sequence
1. Close Phase 5 entry gates, especially D-008.
2. Execute Phase 5 Firewall F1–F8 under PHASE5_PLAN.md.
3. Independently inspect and accept Phase 5.
4. Pre-register and execute Phase 6 Backtest.
5. Independently inspect and accept Phase 6.
6. Pre-register and execute Phase 7 Monitoring.
7. Independently inspect and accept Phase 7.
8. Pre-register and execute Phase 8 Integration.
9. Independently inspect and accept Phase 8.
10. Pre-register and execute Phase 9 Independent Audit.
11. Apply only approved Phase 10 Remediation; re-inspect affected gates.
12. Pre-register and execute Phase 11 DEMO-readiness preparation without enabling DEMO or sending orders.
13. Independent final readiness inspection and completion report.
14. After engineering completion and Phase 11 independent PASS, execute the separate one-time Phase 12 autonomous DEMO validation under D-030 / A-09 (4h30m, DEMO only, XAUUSD.); no LIVE execution is permitted. This validation is separate from engineering completion and retains its own evidence and independent verdict.

## Completion rule
A phase is complete only when its approved criteria are satisfied, required evidence is recorded, and an independent read-only Inspector returns PASS on a frozen snapshot. Developer self-approval never counts.

## Phase 5
Use PHASE5_PLAN.md unchanged unless a new owner-approved decision supersedes it. F1–F8 weights remain 10/12/12/15/15/15/13/8 = 100.

## Phases 6–11
Each phase must have its own plan before implementation. The plan must freeze scope, acceptance criteria, safety boundary, evidence requirements, and independent-inspection rule. Do not assign completion weights until the owner approves a phase plan.

## Safety boundary
- No LIVE mode.
- DEMO remains disabled throughout Phases 5–11. The single post-completion Phase 12 test is separately governed by D-030/A-09; A-05 remains ungranted and is superseded only for that bounded Phase 12 test.
- No account financial-field access without A-04.
- No order construction/submission during Phases 5–10.
- Phase 11 prepares and verifies readiness only; it does not activate execution.
- No live execution test is required for project engineering completion.
- No destructive data operations, history rewrite, force-push, or unrelated-project changes.

## D-008 closure work
D-008 is the current Phase 5 entry blocker. Closure requires real evidence of:
- isolated Python 3.11 environment with system-site-packages disabled;
- pinned dependency versions;
- verified package hashes;
- documented package provenance;
- reproducible offline installation from a documented wheelhouse or equivalent immutable source;
- full suite + compileall + preflight evidence from that environment.
No claimed closure may rely on an inherited/system package or an unverified package source.

## Post-completion Live Verification
This is a separate validation stage, not a prerequisite for engineering completion. The owner may run the approved real-environment verification later and return:
- exact environment/revision;
- timestamps and market/session window;
- commands and exit codes;
- raw outputs/evidence with SHA-256;
- any observed deviations or failures.
The project then receives a separate PASS/FAIL/BLOCKED/REMEDIATION verdict for that validation.