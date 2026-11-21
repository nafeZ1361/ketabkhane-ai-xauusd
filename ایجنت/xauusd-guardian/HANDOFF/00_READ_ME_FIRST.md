# 00 — READ ME FIRST

## Current authoritative state — 2026-11-21

Repository: nafeZ1361/ketabkhane-ai-xauusd
Project: ایجنت/xauusd-guardian/
Accepted baseline branch: fix/w1-timezone-validation
Accepted latest commit: 907f4e37ce63ce2b28a33cb5132d70831032a56e
Current work branch: work/guardian-risk-research-second-brain-audit

Phase 1: PASS (provisional sign-off). Phase 2: ACCEPTED (A-08). Phase 3: ACCEPTED (D-022). Phase 4: ACCEPTED (D-024). Do not reopen them. D-019 remains DEFERRED. The Phase 2 clock recheck is a separate open ticket per D-025; do not claim it passed.

## Read order

1. This file.
2. 01_STATE_SNAPSHOT.md for exact current status and residuals.
3. PROJECT_STATE.md and newest entries in DECISIONS_LOG.md.
4. 02_ROADMAP.md only for authorized workstreams.
5. Read only files directly relevant to the assigned change.

## Non-negotiable boundaries

1. DEMO-only. No live trading, no order submission, no order construction, no live flag.
2. Do not read account Balance/Equity/Margin/Profit until approval A-04 is explicitly recorded.
3. MetaTrader5 imports only inside src/guardian/adapters/; research/domain code is pure.
4. No credentials, account identifiers or secrets in logs, artifacts or Second Brain.
5. No new runtime dependency without written justification and owner approval. Keep Guardian runtime stdlib-first.
6. Never edit applied migrations or existing evidence. Add new numbered migrations only under a separately approved storage change.
7. Never weaken, delete, skip or collect-ignore a test to make a gate green.
8. No force-push, history rewrite, branch deletion or merge to main without explicit approval.
9. Developer cannot issue independent PASS. Inspector must be a separate read-only identity/session on a frozen snapshot. If independence is not proven, report INDEPENDENCE_NOT_ESTABLISHED.
10. Guardian-to-Second-Brain connection is read-only. Second Brain schema is design-only until exact owner command قفل Schema v0.1.

## Verification protocol

For each workstream: source-backed finding → smallest implementation → focused positive and negative tests → full Windows CI → immutable evidence and hashes → independent inspection → owner review. Never claim tests ran unless the exact command and exit code exist.

## Known current constraints

- Existing domain.market.quality already validates OHLC, duplicates, gaps, crossed quotes and stale bars. Extend; do not duplicate.
- scripts/research_edge.py is a single 70/30 holdout ML experiment, not an execution backtester or true walk-forward.
- D-004/D-021 constrain the ML experiment; no pandas/scikit-learn runtime dependency is approved.
- No Second Brain repository was present in the connected GitHub account inventory at audit time; only a schema proposal is placed in this Guardian repo. Create/use a separate repo only after its location is established.
- No MT5 terminal or local Windows runtime is available through this GitHub editing session.

## Start here

Use AUDIT/REPOSITORY_AUDIT_2026-11-21.md for verified findings. Use HANDOFF/02_ROADMAP.md for scoped next work. Do not follow stale status statements in historical reports.
