# Stage Checkpoints, Rollback, and Recovery

**Status:** Proposed project-wide capability; not yet implemented or tested.  
**Applies to:** Every stage from Stage 1 onward.  
**Current scope:** Documentation only on `stage-0/draft-audit-plan`. This document does not authorize Stage 1, code changes, merges, or pushes to `main`.

## Goal

If a stage fails, produces invalid results, or breaks a previously passing check, the project must be able to return to the last known-good state without losing evidence or silently changing the dataset or baseline.

## Core rule

**Every stage starts from a recorded PASS checkpoint and must either produce a new accepted checkpoint or remain BLOCKED.** A failed stage must never overwrite the last known-good checkpoint.

## Required checkpoint contents

Before starting a stage, record a checkpoint manifest containing, where applicable:

- Stage ID and status; UTC creation time.
- Git commit SHA and branch.
- Input dataset identity: path/identifier, SHA-256, row count, and schema. Do not store the private/local CSV in the public repository.
- Configuration, feature/target definitions, thresholds, dependencies, and random seeds.
- Relevant test commands, exit codes, concise outputs, and evidence paths/hashes.
- Last accepted checkpoint ID and the human approval reference for protected actions.

After a stage passes, create a new immutable checkpoint and link its evidence. A checkpoint is not PASS merely because files were saved or an agent says it passed.

## Failure and rollback procedure

1. **STOP:** Stop progression immediately. Do not start the next stage or overwrite the last accepted checkpoint.
2. **CLASSIFY:** Record the failing stage, observed failure, reproduction command, affected files/artifacts, and whether data, configuration, code, dependencies, or assumptions may be involved.
3. **PRESERVE:** Save logs, diffs, test output, manifests, and failed-stage artifacts as evidence. Do not delete or rewrite historical evidence.
4. **SELECT:** Identify the most recent checkpoint whose required tests, validation, integrity, safety, and governance gates passed.
5. **PLAN:** Write a minimal rollback plan stating exact files/state to restore, what must remain unchanged, and the verification tests.
6. **AUTHORIZE:** Rollback that only affects an already-authorized, unprotected local working scope may be prepared within that scope. Changes to protected artifacts, dataset/baseline identity, stage assumptions, shared branches, merge/push, or governance require explicit human approval before action.
7. **RESTORE SAFELY:** Prefer a new rollback/recovery commit or a separate recovery branch. Do not use `reset --hard`, force-push, or delete commits/evidence on shared history. Do not silently replace the original dataset.
8. **VERIFY:** Re-run the checkpoint's required tests and integrity/hash checks. Confirm the restored code/config/data identities match the chosen checkpoint.
9. **RECORD:** Write a recovery record with failure ID, checkpoint ID, actions, diffs, test results, hashes, approval, and final PASS/BLOCKED status.
10. **RESUME:** Resume only after the recovery checks pass and required human confirmation is recorded. Otherwise remain BLOCKED.

## Data and evidence protections

- Source datasets and accepted baselines are immutable. A rollback changes the selected code/configuration state, not the source data itself.
- Keep failed outputs and evidence; label them FAILED or SUPERSEDED instead of deleting them.
- Never edit an old checkpoint in place. Create a new checkpoint or recovery record.
- A changed dataset, target definition, cost assumption, or baseline is a new identity and requires a new manifest and appropriate human approval.
- A rollback does not prove that the previous checkpoint is valid for a changed environment; dependency and reproducibility checks must run again.

## Minimum acceptance tests for the future implementation

- Can list checkpoints in chronological order and identify the latest accepted checkpoint.
- A failed stage cannot replace or mark itself as the last PASS checkpoint.
- Restoring a checkpoint reproduces the recorded code/config/data hashes or reports a clear BLOCKED result.
- Rollback preserves prior logs, manifests, evidence, and failed-stage outputs.
- Invalid, missing, or conflicting checkpoint metadata causes a safe BLOCKED result; no silent fallback.
- Recovery operations do not send broker orders, access broker credentials, or enable live trading.
- A second independent reviewer can follow the recovery record without relying on chat history.

## Current limitation

This is the design contract only. No rollback code, automatic restore behavior, checkpoint tags, or recovery tests have been implemented. The current authorization remains Stage 0 documentation only. The mechanism must be designed and tested before Stage 1 implementation begins, then used at every later stage.
