# AI Start Here — Read Before Doing Any Work

> Purpose: make a new AI/agent understand the project without repeating questions. This file is the mandatory entry point.

## 1. Project identity
- Repository: `nafeZ1361/ketabkhane-ai-xauusd`
- Goal: build an auditable XAUUSD machine-learning research, backtest, and paper-validation system.
- Current stage: **Stage 0 — scope, source-data provenance, and reuse audit**.
- Current status: **BLOCKED**. Stage 1 is not authorized.
- Current work branch: `stage-0/draft-audit-plan`.
- Default branch `main` must remain untouched under the current approval.

## 2. Read in this order
1. `AI_MEMORY/00_START_HERE.md` — this page.
2. `AI_MEMORY/01_CURRENT_STATE.md` — exact current status and next action.
3. `AI_MEMORY/02_TASK_LEDGER.md` — completed, active, blocked, and next tasks.
4. `AI_MEMORY/03_DECISIONS.md` — decisions and non-negotiable boundaries.
5. `AI_MEMORY/04_HANDOFF_PROMPT.md` — compact prompt to start a fresh AI session.
6. `PROJECT_STATE.md` — project state summary.
7. `STAGE_0_AUDIT.md` and `REUSE_DECISION.md` — evidence and old-code review.
8. `PROPOSED_PROJECT_PLAN.md` — proposed stage sequence.

## 3. Rules for every AI
- Read the files above before asking the user anything. Do not ask for information already recorded.
- Treat the repository documents as the project memory. Do not rely on chat history alone.
- First report your understanding in a few lines, then do the next authorized task; do not ask the user to restate the project.
- Do not claim an action, test, hash, or review happened unless evidence is recorded.
- Clearly label facts as verified, user-reported, inferred, or unknown.
- When work changes, update `AI_MEMORY/01_CURRENT_STATE.md` and `AI_MEMORY/02_TASK_LEDGER.md` in the same work session. Record decisions in `AI_MEMORY/03_DECISIONS.md`.
- Keep notes concise but sufficiently detailed for another agent to continue. Link evidence by repository path, commit, and test output where possible.
- If a blocker exists, investigate it within authorized scope and document it; do not simply ask the user to do the investigation.
- Never silently broaden scope or treat silence as approval.

## 4. Frozen safety boundary
Research, backtesting, and paper validation only. No live trading, real orders, broker credentials, autonomous execution, or production deployment. No copying old code/data until explicitly reviewed and approved. No modifying `main`, merging, or starting Stage 1 under the current scope.

## 5. How to continue
Use `AI_MEMORY/01_CURRENT_STATE.md` for the single current next action. Check the task ledger for prerequisites. Work only within the authorized scope, gather evidence, update the memory, and leave the project BLOCKED if acceptance evidence is incomplete.

Last initialized: 2026-10-15. Maintainer must keep this memory current.
