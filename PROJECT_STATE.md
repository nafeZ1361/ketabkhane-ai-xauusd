# Project State

**Current stage:** "0"  
**Stage status:** BLOCKED  
**Last updated:** 2026-10-15  
**Branch:** `stage-0/draft-audit-plan`

## Repository
- Canonical repository: `nafeZ1361/ketabkhane-ai-xauusd`
- Default branch: `main`
- Starting/main commit: `de4e4507ab12acb0db79bb88e649f7c3662de80a`
- Stage 0 documentation and audit updates are on the separate draft branch only.

## Completed
- [x] Created the isolated Stage 0 draft branch.
- [x] Added four Stage 0 documents.
- [x] Inventoried and statically reviewed the five files in the old repository's `backtest/` folder.
- [x] Recorded candidate-level reuse decisions; no file approved for transfer.

## Blockers
- Dataset provenance, license, and redistribution permission need evidence.
- MT5 server/source, timezone/timestamp convention, symbol details, and data coverage need confirmation from available project records.
- Deeper function-level tests are needed before any legacy backtest component can be reused.
- No Stage 0 acceptance evidence package or independent human approval exists yet.

## Next action
Continue Stage 0 evidence collection and static audit only. Do not copy files, run the legacy trading/backtest scripts, change `main`, or start Stage 1. Keep status BLOCKED until evidence is complete and a human explicitly approves the exact scope.

## Safety
No live trading or real orders. No credentials. No production deployment. No merge or changes to `main` under this scope.
