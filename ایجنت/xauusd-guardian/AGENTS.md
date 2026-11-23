# AGENTS.md — working rules for this repository

Scope: this nested project directory only (`ایجنت/xauusd-guardian/`). The containing Git repository is `ketabkhane-ai-xauusd`; its root-level `AGENTS.md` governs the parent project, not this nested project's implementation. Do not modify files outside this directory unless a specific owner-approved task explicitly requires it. This file governs work inside this directory and must not be interpreted as permission to alter sibling projects.

## Authority and precedence

- The repository-root `AGENTS.md` continues to apply its repository-wide baseline restrictions (including secret/market-data handling, file-size limits, and the read-only `legacy/source/` archive).
- This nested file adds Guardian-specific implementation and safety rules only within `ایجنت/xauusd-guardian/`; it does not cancel or weaken repository-root restrictions.
- Where both files apply, satisfy both. If requirements appear to conflict, apply the stricter restriction and stop for owner clarification when the conflict cannot be safely resolved.
- Any future `AGENTS.md` below this directory applies only to its descendants and may narrow scope, but may not weaken the hard rules in this file.
- Neither this file nor a child instruction grants permission to modify parent or sibling project paths.


## Hard rules

1. DEMO only. There is no live mode, no live flag, no override. Do not add one.
2. `MetaTrader5` may be imported **only** inside `src/guardian/adapters/`. `order_send`, `order_check`, and any trade request construction are forbidden everywhere in Phase 1–4 and, after Phase 5, allowed **only** in `firewall_process/`.
3. Never read `balance`, `equity`, `margin*`, `profit` from the account until approval A-04 exists in `approvals/`.
4. Never log account numbers, credentials, tokens, or secrets. All log output passes the redaction filter.
5. Fail closed: unknown config keys, unknown message fields, missing data, ambiguous symbols → stop, do not guess.
6. Do not weaken, delete, or skip tests to make a gate green. Do not edit evidence.
7. No new dependency without a written justification and human approval. Banned without approval: pandas, numpy, scipy, matplotlib.
8. Standard library first: `dataclasses`, `sqlite3`, `logging`, `decimal`, `statistics`, `tomllib`.
9. Preserve history. No force-push, no reset of user history, no rewriting unrelated files.
10. Every behaviour change → test + evidence + `DECISIONS_LOG.md` entry if it changes a contract.

## Workflow per change

inspect state → identify blast radius → smallest edit → unit tests → regression tests → record evidence → update `PROJECT_STATE.md`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\preflight.py
```

Report actual output and exit codes. "Should pass" is not evidence.
