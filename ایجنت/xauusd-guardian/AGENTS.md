# AGENTS.md — working rules for this repository

Scope: `xauusd-guardian`. Other user projects (e.g. `ketabkhane-ai-xauusd`) are out of scope and must never be touched.

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
