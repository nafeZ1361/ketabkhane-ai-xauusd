# Phase 3 — Gate S7, Round 7: the four open items

Developer: the inspector who also wrote the round-4/5 fixes (not the S1–S6 author)
Date: 2026-11-15
Tree: branch `fix/w1-timezone-validation`, committed HEAD `e56b3a69b007e3c797a1a6952e6605d0e787935a`,
S7 work uncommitted.
Scope: **only** the four items left open by rounds 5–6. No S1–S6 behaviour was changed, no
commit, no push.

**Verdict: not PASS.** This is the developer-side record. S7 requires an independent
inspection (command in §7).

---

## 1. Item 1 — single-quoted identifiers (phantom `if`)

**Cause.** `_CREATE_RE`'s `IF NOT EXISTS` group is optional, so for
`CREATE TABLE IF NOT EXISTS 'probe_sq'` the engine backtracked, skipped that group and
matched the bare identifier `IF` as the object name. `_created_objects` then returned
`{'if': 'table'}`, the adoption guard saw nothing to refuse, and the refusal that did
happen named a phantom object.

**Change.** `_CREATE_RE` now carries `(?!IF\b)` before the name group, so it cannot
attribute the keyword. The new `_unattributed_create` helper inspects every statement
that starts with `CREATE` and refuses the first one the parser cannot attribute.

**Behaviour after.** Single-quoted identifiers remain **refused** — the safety property
is unchanged, only the diagnostic:

```
MigrationError: migration 0004_probe.sql contains a CREATE this project does not support:
"CREATE TABLE IF NOT EXISTS 'probe_sq' (id TEXT NOT NULL);". S7 scope is CREATE TABLE and
CREATE INDEX only; views, triggers, TEMP objects and identifier spellings the parser cannot
attribute are refused rather than recorded.
rows=1  hist=[1, 2, 3]
```

The operator table and its row are untouched, and the message names the statement —
never `'if'`.

## 2. Item 2 — `ON DELETE SET DEFAULT` (must-fix)

**Cause.** The FK pre-flight refused `CASCADE` and `SET NULL` but not `SET DEFAULT`,
which also rewrites child rows when the parent is dropped.

**Change.** The refused action set is now `{"CASCADE", "SET NULL", "SET DEFAULT"}`; the
docstring and the error text say so.

**Proof (executed).** A child table
`run_ref TEXT NOT NULL DEFAULT 'none' REFERENCES signal_runs(run_id) ON DELETE SET DEFAULT`
holding `'r1'`:

```
MigrationError: reverting 0003_signals.sql would drop a table that ['operator_child ->
signal_runs ON DELETE SET DEFAULT'] references with ON DELETE CASCADE/SET NULL/SET DEFAULT;
rows this migration did not create would be deleted. Drop or detach those tables first.
child_run_ref=r1   hist=[1, 2, 3]
```

The child value is still `r1`; the reverse is refused, not partly applied.

## 3. Item 3 — `CREATE VIEW` / `CREATE TRIGGER`

**Decision: out of scope, enforced by refusal.** S6's reverse whitelist only understands
`DROP TABLE` / `DROP INDEX`, and provenance is measured over tables and indexes;
supporting views and triggers would require a symmetric drop path that does not exist.
Rather than leave an apply-record-revert asymmetry, any `CREATE` other than
`TABLE`/`INDEX` is refused before it runs, and the contract is stated in the module
docstring (safety model item 5).

| Statement | Result |
|---|---|
| `CREATE VIEW probe_v AS SELECT …` | refused, `hist=[1, 2, 3]` |
| `CREATE TRIGGER probe_tr AFTER INSERT … BEGIN … END;` | refused, `hist=[1, 2, 3]` |
| `CREATE TEMP TABLE probe_tmp (id TEXT)` | refused, `hist=[1, 2, 3]` |
| `CREATE TABLE probe_ok (…)` + `CREATE INDEX idx_probe_ok …` | **applies**, `applied=[4]`, `prov=(('index','idx_probe_ok'),('table','probe_ok'))` |

## 4. Item 4 — ATTACH regression test

**Added in-repo:** `test_revert_never_touches_an_attached_schema`. It attaches a database
holding its own `signals`, runs `revert_migration(conn, …, 3)` and asserts the reverse is
refused (`left objects behind`), the attached rows survive, and the ledger is unchanged.

```
err = MigrationError: reversal of 3 left objects behind: ['side:signals']
side_rows=1   main_signals=1   hist=[1, 2, 3]
```

Fail-closed is preserved: the whole reverse rolls back inside its transaction.

## 5. Tests and results

| # | Command (copy `C:\GS7\r7`, byte-identical to the tree) | Exit | Result |
|---|---|---|---|
| 1 | `python -m pytest -q --junitxml=…` | 0 | **tests=292 failures=0 errors=0 skipped=0** (43.8 s) |
| 2 | `python -m pytest tests/unit/test_migration_reversal.py -k "single_quoted or create_view or create_trigger or set_default or attached_schema" -v` | 0 | **5 passed**, 35 deselected |
| 3 | `python -m compileall -q src scripts tests` | 0 | clean |
| 4 | `probe_round7.py` (items 1–4, 7 scenarios) | 0 | **7/7** |
| 5 | `probe_s7r4.py` (round-4 15 scenarios, regression) | 0 | **15/15** |
| 6 | `probe_round5_cases.py` (round-5 repros, regression) | 0 | **7/7** |

Suite history: 279 (F1c) → 282 (round 4) → 287 (round 5) → **292** (round 7).

Five tests added: `test_single_quoted_identifier_is_refused_by_name`,
`test_create_view_is_refused`, `test_create_trigger_is_refused`,
`test_revert_refuses_a_set_default_child_table`,
`test_revert_never_touches_an_attached_schema`.

## 6. Files changed

| File | SHA-256 (worktree) |
|---|---|
| `src/guardian/storage/db.py` | `2a4ad1889dbeefe6e0115476be42c0ff8618181653f6c93881ed8e47e03193ab` |
| `tests/unit/test_migration_reversal.py` | `43473b360068d453d1cd11d99de30264091a286341fda258d51a4264c9111c81` |
| `PROJECT_STATE.md` | bookkeeping only |
| `HANDOFF/01_STATE_SNAPSHOT.md` | bookkeeping only |
| `HANDOFF/MANIFEST.sha256` | regenerated |
| `evidence/phase3-S7R7-<stamp>.txt` | new, with `.sha256` sidecar |

No other path changed. `git diff --stat` shows 5 files: `db.py` +119/−…, the test file
+215, and the three bookkeeping files.

## 7. Independent inspection command

```
cd C:\Users\icFixer.ir\AppData\Roaming\AutoClaw-oversea-official\accounts\41daec57d4756a03ca8efb2086ae29e4998b4a2ee8e2540c2e48ca7db7cf9831\projects\ایجنت\xauusd-guardian\ایجنت\xauusd-guardian
git status --short ; git diff --stat
# copy the subtree to a short path first (the path is ~200 chars):
robocopy . C:\GS7\rev7 /E /XD .git .venv __pycache__ .pytest_cache data logs
cd C:\GS7\rev7
$env:PYTHONDONTWRITEBYTECODE="1"
<venv>\python.exe -m pytest -q
<venv>\python.exe -m compileall -q src scripts tests
```

where `<venv>` is
`C:\Users\icFixer.ir\AppData\Roaming\AutoClaw-oversea-official\accounts\7f9fa7c15983c9654b410a0d812b523be39e835c034f44ac0c2e8061a1288073\projects\ایجنت\xauusd-guardian\.venv\Scripts\python.exe`.

## 8. Residuals (unchanged, recorded)

| # | Residual | Status |
|---|---|---|
| R1 | a missing `main` table surfaces as `OperationalError` at DROP time | open, accepted (fail-closed) |
| R2 | a database without `schema_objects` fails as `OperationalError` | open, accepted |
| R3 | a same-named object in `temp` makes the post-condition refuse | open, accepted (over-strict) |
| R4 | shape equality is treated as provenance; a same-shape replacement table would be dropped | open — needs a recorded identity token |
| R5 | data-only migrations are impossible by design | accepted, stated in the error |
| R6 | `MANIFEST.sha256` does not cover `evidence/` | open, accepted |
