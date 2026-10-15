# Task Ledger

This is the durable work log. Update task status and evidence whenever work changes.

Statuses: `DONE`, `IN_PROGRESS`, `BLOCKED`, `NOT_STARTED`. A task is not DONE without evidence.

## Stage 0 tasks

| ID | Task | Status | Evidence / notes |
|---|---|---|---|
| S0-001 | Create separate Stage 0 branch; preserve main | DONE | `stage-0/draft-audit-plan`; main baseline `de4e4507ab12acb0db79bb88e649f7c3662de80a` |
| S0-002 | Write initial audit, reuse decision, proposed plan, project state | DONE | Root docs: `STAGE_0_AUDIT.md`, `REUSE_DECISION.md`, `PROPOSED_PROJECT_PLAN.md`, `PROJECT_STATE.md` |
| S0-003 | Inventory old repository backtest folder | DONE | Static source review at old repo main `36df7c9665ded188ab565d1fd4f25da63197c0f3`; details in `STAGE_0_AUDIT.md` |
| S0-004 | Review CSV replay timing/cost/timezone risks | DONE | Static review only; `run_csv_backtests.py` not approved as-is |
| S0-005 | Record user's local CSV metadata and SHA256 | DONE | `AI_MEMORY/01_CURRENT_STATE.md`; user-provided PowerShell output |
| S0-006 | Scan all CSV rows for malformed records, duplicates, ordering, OHLC validity, gaps | DONE (user-output reviewed) | User-provided full scan: 3,489,359 rows; wrong columns 0; invalid numerics 0; OHLC/negative-value issues 0; adjacent duplicate timestamps 0; out-of-order timestamps 0; zero VOL 3,251,252; zero TICKVOL 3; zero SPREAD 57. Gap scan: 6,505 gaps >60s; 538 >12h; longest 451,560s. Outputs are user-provided, not independently reproduced. Gap causes and timezone remain unverified. |
| S0-007 | Verify MT5 export method, server/timezone, symbol specification | BLOCKED | Need non-secret MT5 metadata/export settings; no credentials |
| S0-008 | Establish data rights and public-repository handling | BLOCKED | User owns local export claim does not establish redistribution rights; dataset must not be committed |
| S0-009 | Finalize code reuse choices and acceptance criteria | IN_PROGRESS | No source files approved for transfer |
| S0-010 | Independent review and Stage 0 exit decision | NOT_STARTED | Cannot pass by inference; requires evidence and explicit human approval |
| S0-011 | Start Stage 1 data audit | BLOCKED | Not authorized until Stage 0 exit requirements pass and human confirms |

## Session log

### 2026-10-15
- User requested persistent project memory comparable to Obsidian so a new AI can resume without repeating questions.
- Created repository-native Markdown memory structure under `AI_MEMORY/`.
- User-provided local CSV metadata and full-file scan outputs recorded; no CSV uploaded or committed.
- User instructed the project to proceed on a working assumption that the data is usable for backtesting/ML; this is an assumption, not an integrity PASS.
- Scope remains documentation and Stage 0 only; no implementation code has been authorized.

## How to update this ledger
1. Mark the task status.
2. Add evidence link/path, commit SHA, command/output location, or a clear reason it remains blocked.
3. Update `AI_MEMORY/01_CURRENT_STATE.md` if the next action or blocker changes.
4. Record any material new decision in `AI_MEMORY/03_DECISIONS.md`.
5. Never mark PASS based only on a narrative claim without evidence.
