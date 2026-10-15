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
- User-provided full-file structural scan output is recorded in AI_MEMORY/01_CURRENT_STATE.md and AI_MEMORY/05_EVIDENCE_INDEX.md. The scan found no malformed column counts, invalid numeric values, OHLC/negative-value issues, adjacent duplicate timestamps, or out-of-order timestamps. It found 6,505 gaps >60 seconds, including 538 >12 hours; longest 451,560 seconds. Gap causes are not fully classified.
- Dataset source timezone, timestamp convention, symbol specification, and export settings still need evidence.
- Data use and public redistribution rights are not established.
- No Stage 0 acceptance evidence package or independent review exists.
- No legacy source file is approved for transfer.

## Next action
Continue Stage 0 only. Record and use the user-provided structural scan output. The user asked us to treat the CSV as usable for initial research/backtesting and not to continue investigating the gaps for now; record that as a working assumption, not a verified integrity PASS. Resolve the remaining Stage 0 provenance and reuse-review blockers. Do not implement the backtester or start Stage 1 until explicitly authorized after Stage 0 exit. Do not ask broad questions already answered in memory. Do not copy code/data, run legacy trading scripts, change main, merge, or start Stage 1.

## Safety
No live trading or real orders. No credentials. No production deployment. No merge or changes to `main` under this scope. The local CSV must not be committed to this public repository.
