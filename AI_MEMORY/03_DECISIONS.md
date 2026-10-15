# Decisions and Non-Negotiable Constraints

## DEC-001 — Repository-native memory, not an app installation
**Date:** 2026-10-15  
**Decision:** Use Markdown files stored in the project repository as the durable project memory, organized like a small Obsidian vault.  
**Reason:** Any AI that can read the repository can load the project goal, state, decisions, evidence, and next task without depending on chat history. No Obsidian installation is required for the memory to work. Obsidian may optionally open the folder later.  
**Scope:** Documentation only on `stage-0/draft-audit-plan`; not merged into main.

## DEC-002 — Keep main unchanged during Stage 0
**Decision:** All Stage 0 documentation remains on `stage-0/draft-audit-plan`.  
**Reason:** User explicitly instructed not to touch main and not to start Stage 1 before Stage 0 approval.

## DEC-003 — No legacy code/data copied without review and explicit approval
**Decision:** No files from `nafeZ1361/golden-librarytallaii` are approved for transfer at this point.  
**Reason:** Static review found execution side effects and possible backtest timing/data assumptions. The old repo also contains an option to enable live trading, incompatible with the new project's boundary.

## DEC-004 — Strict research-only safety boundary
**Decision:** No live trading, real orders, broker credentials, autonomous execution, or production deployment.  
**Reason:** The project is for ML research, backtesting, and paper validation only.

## DEC-005 — No inferred PASS
**Decision:** UNKNOWN, INCOMPLETE, or FAIL cannot be treated as PASS. A stage only advances after acceptance evidence, review, and explicit human approval.

## DEC-006 — Dataset stays out of the public repository
**Date:** 2026-10-15  
**Decision:** Do not upload or commit the local 205 MB CSV to the public repository.  
**Reason:** It is unnecessary for metadata checks and data redistribution rights have not been established. Store only hashes, schema, quality summaries, and approved small synthetic fixtures if later needed.

## Open decisions
- Confirm exact broker server and timestamp convention from MT5 export metadata.
- Confirm whether dataset can legally be used for research and whether any redistribution is permitted.
- Final accept/reject/defer decision for any extracted pure backtest logic.
- Stage 0 exit approval.


## DEC-007 — Rollback and recovery is a required project capability
**Date:** 2026-10-15  
**Decision:** Before Stage 1 starts, define and later implement a checkpoint/rollback mechanism usable at every stage.  
**Required behavior:** Every stage starts from a recorded known-good checkpoint; failed-stage artifacts and evidence are preserved; rollback uses traceable recovery commits/branches, verifies hashes and tests, and cannot silently replace data/baselines or erase history. Protected changes, shared-branch actions, and stage transitions still require explicit human approval.  
**Design reference:** `ROLLBACK_AND_RECOVERY.md`.  
**Status:** Requirement accepted; design documented on the Stage 0 draft branch. Implementation and tests are not yet done. This decision does not authorize Stage 1 or changes to `main`.
