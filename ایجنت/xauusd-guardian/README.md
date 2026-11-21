# XAUUSD Guardian

DEMO-only, offline-first XAUUSD research system. Python 3.11, standard library first.

**LIVE TRADING IS UNSUPPORTED AND PROHIBITED. No order API is added by this work.**

## Authoritative status (2026-11-21)

- Phase 1: PASS (provisional sign-off status as recorded in PROJECT_STATE.md).
- Phase 2: ACCEPTED under A-08. The separate PHASE2-CLOCK-RECHECK-1 ticket is tracked independently; see D-025.
- Phase 3: ACCEPTED under D-022.
- Phase 4: ACCEPTED under D-024.
- D-019: DEFERRED; research modules/tests remain out of scope / NOT_RUN unless separately approved.
- Phase 5: NOT STARTED. No order firewall or order submission is authorized.
- This branch contains post-acceptance remediation and research/monitoring design work. It does not reopen Phases 1–4 or alter their acceptance records.

Read HANDOFF/00_READ_ME_FIRST.md and HANDOFF/01_STATE_SNAPSHOT.md before working. PROJECT_STATE.md and the append-only DECISIONS_LOG.md are authoritative; historical handoff reports remain historical evidence and must not override newer decisions.

## Safety

- DEMO-only; no live mode, no live orders, no order construction.
- No account Equity/Balance/Margin/Profit reads until approval A-04 exists.
- MetaTrader5 imports only inside src/guardian/adapters/.
- No new runtime dependency without a written decision and approval.
- Never edit applied migrations or existing evidence.
- Every behavior change needs focused regression tests and evidence; independent PASS is issued only by a separate read-only Inspector.

## Run (Windows / approved Python 3.11)

\`\`\`powershell
.\\.venv\\Scripts\\python.exe -m pytest -q
.\\.venv\\Scripts\\python.exe -m compileall -q src scripts tests
.\\.venv\\Scripts\\python.exe scripts\\preflight.py
\`\`\`

## Current work documents

- AUDIT/REPOSITORY_AUDIT_2026-11-21.md — confirmed source findings and limitations.
- docs/second-brain/SCHEMA_PROPOSAL_v0.1.md — design only; not locked and not implemented.
- docs/claude-skills/ADOPTION_POLICY.md — pinned sources, license decisions and adoption policy.
- docs/claude-skills/GUARDIAN_EXECUTION_CHECKLISTS.md — extracted, testable Guardian procedures.
- HANDOFF/02_ROADMAP.md — authorized workstreams and acceptance gates.

## Layout

\`\`\`text
src/guardian/{contracts,domain,application,adapters,storage,audit,observability}/
migrations/                 # append-only; never edit applied migrations
tests/{unit,security}/
scripts/                     # read-only/research CLI tools
data/ logs/ reports/ evidence/
\`\`\`
