# 00 — READ ME FIRST (agent handoff)

You are picking up an in-progress project. Read this page, then exactly one more file.
Everything else is optional and only worth its tokens if your task touches it.

## What this is

`nafeZ1361/ketabkhane-ai-xauusd` · project directory `ایجنت/xauusd-guardian/`
A DEMO-only, offline-first XAUUSD research system. Python 3.11, standard library first.

## State in one paragraph

Phase 3 (analysis & strategy) is **in progress**. Stages S1–S5 are PASS. S6 (migration 0003
additive + reversible) is **PASS as of the S6 inspection**, committed as `2e56ae7`. The S7 independent
review then returned **BLOCK three times**: F1 (a pre-existing same-named table could be adopted and
then dropped by the reverse), F1b (identifiers compared case-sensitively while SQLite is not), F1c
(no measured provenance, unqualified drops reaching `TEMP`/attached schemas, quoted declarations
unparsed). **All three are fixed**: adoption refused at apply, names compared case-insensitively,
provenance measured into `schema_objects`, every reverse DROP qualified with `main.` and post-checked
across all schemas, legacy databases refused a reverse; suite 279/279, awaiting re-review. Phase 4 and
everything after it is **NOT AUTHORIZED**.

## Hard rules — do not negotiate these

1. **DEMO only.** There is no live mode, no live flag, no override. Do not add one.
2. `MetaTrader5` may be imported **only** inside `src/guardian/adapters/`. No `order_send`,
   no `order_check`, no trade-request construction anywhere else.
3. Never read `balance`, `equity`, `margin*`, `profit` — no approval A-04 exists.
4. Never log account numbers, credentials, tokens or secrets (redaction filter must stay in place).
5. **No git write or network operation without an explicit human go-ahead.** That means no commit,
   push, pull, fetch, merge, rebase, reset, amend, stash, branch deletion, or `git add -A`.
6. No new dependency without a written justification and human approval. pandas/numpy/scipy/
   matplotlib are banned without approval.
7. Never edit an **applied** migration. Its SHA-256 is pinned in `schema_migrations`; editing it
   makes every applied database refuse to migrate. Add a new numbered migration instead.
8. Never edit a file under `evidence/`. Add a new timestamped file.
9. Do not weaken, delete or skip a test to make a gate green. A red test is information.
10. Fail closed: unknown config key, unknown field, missing data, ambiguous symbol → stop.

## Verify before you trust

Run from `ایجنت/xauusd-guardian/`. The approved interpreter on this machine is
`C:\Python311\python.exe` (3.11.8, pytest 9.2.0). A `.venv` per approval A-02 is acceptable.

```powershell
C:\Python311\python.exe -m pytest -q                     # expect 279 passed
C:\Python311\python.exe -m pytest tests/unit/test_migration_reversal.py -q   # expect 27 passed
C:\Python311\python.exe -m compileall -q src scripts tests                   # expect exit 0
git status --porcelain            # compare with 01_STATE_SNAPSHOT.md
```

If the counts differ from `01_STATE_SNAPSHOT.md`, **the tree moved**: re-read the snapshot section
"S6 working tree" and treat the difference as the first thing to explain. Do not assume the docs
are newer than the code.

## Reading order (spend tokens deliberately)

| Read | When |
|---|---|
| `01_STATE_SNAPSHOT.md` | always — exact commits, hashes, residuals |
| `02_ROADMAP.md` | only if you are planning or starting a new stage |
| `03_AGENT_PROTOCOL.md` | always before your first edit |
| `04_PROMPT_TEMPLATES.md` | if you need a ready-to-paste brief |
| `artifacts/*` | only when auditing S6 itself |

Never bulk-read `src/` or `tests/`. Use `rg` for the symbol you need.

## Known traps in this workspace

- The project path contains Persian letters (`ایجنت`). Some tools mangle it; `git`, Python and
  pytest handle it. Quote paths.
- PowerShell 5.1 reads a BOM-less `.ps1` as ANSI and corrupts non-ASCII literals. Keep helper
  scripts ASCII-only, or save them UTF-8 **with BOM**.
- Files are checked out with CRLF on this machine while git stores LF. SHA-256 in `evidence/`
  is over **raw bytes**; `git hash-object` and `sha256sum` of the working file can differ from the
  blob. State which one you measured.
- `git add -A` would sweep in the untracked S5 evidence file. Always add explicit paths.
- `origin/fix/w1-timezone-validation` is in sync as of `f3f6644` (pushed 2026-11-12). Before that,
  the S5 commit existed only locally. Pushing is still a human-authorized action, not a routine one.

## What to do next

The next authorized gate is **S7**. Its first review returned `BLOCK` on F1; the fix is committed and
`02_ROADMAP.md` §S7 has the acceptance criteria for the re-review; `04_PROMPT_TEMPLATES.md` §1 has a
ready brief. Do not start Phase 4 before S7 passes and a human says so.

## If something is ambiguous

Stop and write the question into your report. Guessing is a defect, not a shortcut. The project's
own rule (AGENTS.md) is: *"Should pass" is not evidence.*
