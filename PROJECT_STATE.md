# Project State

**Current stage:** "0"  
**Stage status:** BLOCKED  
**Last updated:** 2026-10-15  
**Branch:** `stage-0/draft-audit-plan`

## Repository
- Canonical repository: `nafeZ1361/ketabkhane-ai-xauusd`
- Default branch: `main`
- Starting/main commit: `de4e4507ab12acb0db79bb88e649f7c3662de80a`
- Stage 0 documents and AI memory exist on the separate draft branch only.
- Mandatory AI entrypoint: `AI_MEMORY/00_START_HERE.md`.

## Completed
- [x] Created the isolated Stage 0 draft branch; main remains untouched.
- [x] Added initial audit, reuse decision, proposed plan, and state documents.
- [x] Inventoried and statically reviewed five files in the old repository's `backtest/` folder and related replay modules.
- [x] Recorded candidate-level reuse decisions; no file approved for transfer.
- [x] Created an Obsidian-style, repository-native Markdown memory system: start page, current state, task ledger, decisions, new-agent handoff prompt, and evidence index.
- [x] Added README links to project memory.
- [x] Recorded local CSV metadata supplied by the user in `AI_MEMORY/01_CURRENT_STATE.md`; dataset itself was not uploaded.

## Blockers
- Full-file CSV quality scan output is not yet available.
- Dataset source timezone, timestamp convention, symbol specification, and export settings need evidence.
- Data use and public redistribution rights are not established.
- No Stage 0 acceptance evidence package or independent review exists.
- No legacy source file is approved for transfer.

## Next action
Continue Stage 0 only. Obtain the read-only CSV quality scan output already requested from the user's Windows PowerShell; record results in the audit and AI memory. Then resolve timezone/provenance and reuse-review blockers. Do not ask broad questions already answered in memory. Do not copy code/data, run legacy trading scripts, change main, merge, or start Stage 1.

## Safety
No live trading or real orders. No credentials. No production deployment. No merge or changes to `main` under this scope. The local CSV must not be committed to this public repository.
