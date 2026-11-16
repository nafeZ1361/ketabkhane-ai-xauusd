# F1 Option 3 — Independent Inspection Report

**Tree under review:** `C:\GS7\opt3` (read-only) · **Date:** 2026-11-15 · **Inspector:** independent reviewer, not the author.

**Environment:** `C:\Users\icFixer.ir\AppData\Roaming\AutoClaw-oversea-official\accounts\7f9fa7c15983c9654b410a0d812b523be39e835c034f44ac0c2e8061a1288073\projects\ایجنت\xauusd-guardian\.venv\Scripts\python.exe` — Python 3.11.8, pytest 9.2.0, SQLite 3.43.1. All probes ran with `cwd=C:\GS7\opt3` and `PYTHONDONTWRITEBYTECODE=1`; scratch DBs, `PYTHONPYCACHEPREFIX` and pytest `cache_dir` were kept under `C:\GS7\review-opt3\`.

**Read-only proof:** sha256 manifest of the whole tree before and after the inspection — 240 files, **0 added, 0 removed, 0 changed**. The 54 `.pyc` files and `.pytest_cache` in the tree pre-date this inspection (author's runs) and are byte-identical.

## 1. Verdict — PASS

No must-fix. The destructive execution path is gone: `revert_migration` raises before doing anything (`db.py:810-824`), and no code in `src/` or `scripts/` executes `DROP`/`DELETE` (`grep executescript` → no matches; the only `DROP`/`DELETE` text in the module is built for the emitted string at `db.py:801-806`). Emission is inert — `sqlite_master`, all row counts and the ledger were identical before/after `emit_reverse_sql` on a freshly applied database — and the emitted script has the required shape. The full suite is 297 passed / 0 failed / 0 skipped, `compileall` is clean, every emit-time precondition still refuses in the expected way, and the CASE A2 operator row survived both library calls. Two documentation gaps (the claimed option-3 report does not exist; several docstrings/headers still describe the removed executed-reverse model) and one contrived qualification gap are recorded below; none of them changes runtime behaviour.

## 2. Must fix

None. No finding met the bar (wrong result, violated requirement, security risk, or a real-world trigger).

## 3. Worth considering

### W1 — the claimed option-3 report does not exist
- **Location:** `HANDOFF/artifacts/REPORT-F1-OPTION3.md` (named in the handoff). Absent.
- **Evidence:** recursive name search over all of `C:\GS7` for `*OPTION3*` / `*option3*` returned nothing. The F1 reports that do exist are `HANDOFF/artifacts/REPORT-F1-INSPECTION.md` — which inspects `C:\GS7\snap-f1`, records `db.py` `d836da1b…18f6` and 295 tests, i.e. a different tree and state — and `REPORT-F1-REMEDIATION.md` (pre-option-3).
- **Impact:** the handoff claims a report that cannot be produced; a reviewer without the ability to re-run the suite has nothing to check the change against, and the author's own rationale for option 3 is unavailable.
- **Fix direction:** either write the report at the claimed path, or correct the handoff to name what actually exists.

### W2 — documentation still describes the removed executed-reverse model
- **Locations and quotes:**
  - `src/guardian/storage/db.py:5-6` — "Their reverses live in ``migrations/rollback/`` and are executed only by :func:`revert_migration`."
  - `db.py:15-24` — safety model items 3–5: "runs inside one transaction", "After the reverse, every schema is re-inspected", "A reverse proceeds only while every signal matches".
  - `db.py:71` — ReversalPlan docstring: "Everything :func:`revert_migration` is about to do, checked beforehand."
  - `migrations/rollback/0003_signals.down.sql:1` — "Reverse of 0003_signals.sql, executed only by guardian.storage.db.revert_migration."
  - `migrations/0003_signals.sql:4-11` — "Reverse (S6) is deliberately NOT implemented in this stage … recorded as a documented manual statement instead of a `0003_*_down*.sql` file" (the down file exists at `migrations/rollback/0003_signals.down.sql`).
  - `tests/unit/test_migration_reversal.py:1` — "reversible, by execution rather than by text".
  - `PHASE3_PLAN.md:42`, `DECISIONS_LOG.md:133` — both still say `revert_migration` executes the drops.
- **Problem:** the shipped code at `db.py:810-824` raises `MigrationError` and holds no DDL; the module docstring, the down-file header and the 0003 header all state the opposite. The 0003 header also contradicts the repository's own contents.
- **Impact:** the module docstring is the safety model an auditor reads first; it currently tells them the library executes reversals. An operator reading the down-file header is told the library will run it. No runtime effect.
- **Fix direction:** restate items 3–5 in emit terms (the script targets `main`, is reviewed and run by a human), correct the down-file and 0003 headers, and add a superseding `DECISIONS_LOG` entry instead of rewriting the historical one.

### W3 — the emitted script's ledger deletes are not `main.`-qualified
- **Location:** `src/guardian/storage/db.py:804-805`.
- **Problem:** the `DROP` lines are `main.`-qualified (`db.py:803`); the three `DELETE FROM schema_*` lines are not. SQLite resolves an unqualified name against `temp` first — demonstrated with a scratch DB: with `temp.t` present, `DELETE FROM t WHERE version = 3` left `main.t` at 1 row.
- **Impact:** if the connection running the script holds a temp table named `schema_migrations`, `schema_objects` or `schema_object_identity`, the script drops the real tables but leaves the ledger rows, so a later `apply_migrations` silently no-ops and the ledger claims 0003 is still applied. Requires a contrived session, hence not must-fix.
- **Fix direction:** emit `DELETE FROM main.<table> WHERE version = …`.

## 4. Record only

- `_all_inventories` (`db.py:205`) is never called; `_schema_list` (`db.py:196`) is used only by it. Dead code that suggests a multi-schema check which no longer exists.
- `CREATE TEMP TABLE schema_migrations(version)` in the caller's session makes `migration_history` (`db.py:464`) raise raw `sqlite3.OperationalError: no such column: filename` instead of `MigrationError`. Fails closed; contrived.
- `tests/unit/test_migration_reversal.py:25-38` defines a test-local operator stand-in named `revert_migration` that calls `conn.executescript(script)`; it is test code, not library code, but a grep-based review may misread it as a surviving destructive path.
- The tree contains a pre-existing `.pytest_cache` and 54 `.pyc` files from the author's runs; my manifest diff shows them unchanged.
- `HANDOFF/artifacts/REPORT-F1-INSPECTION.md` describes `snap-f1`; its 295-test figure and `d836da1b…` hash must not be cited as opt3 evidence.

## 5. Evidence per item

### E1 — hash claims
```
(Get-FileHash -Algorithm SHA256 -LiteralPath 'src\guardian\storage\db.py').Hash.ToLower()
→ 51aa633de9d777b762c62c53349821077d1c0f81c63956afbbec4bb1ec1c792d   (33,655 bytes)

tests/unit/test_migration_reversal.py
→ b77d59d6de247127174c0ac3e38058e255a69f6b7923f39362a1f3fd576f8874   (38,459 bytes; 879 lines; 43 `def test_`)
```
Both match the handoff (`51aa633d…c792d`, `b77d59d6…f8874`). The "tests" hash refers to this one file, not the suite.

### E2 — no destructive execution path
- Every `DROP` / `DELETE FROM` occurrence in `db.py` (`Select-String -Pattern 'DROP|DELETE FROM'`) falls into: the `_DROP_RE` validator (`53-56`, used only to validate down-file text at `600`), comments/docstrings (`15, 22, 127, 230, 276-308, 548-574, 586-629, 637-673, 764, 814`), refusal messages, or the two string-building lines `803` and `805`. No line executes a `DROP` or `DELETE`.
- `revert_migration` (`810-824`) is a docstring plus `raise MigrationError("automated reversal has been removed: …")`; no DDL in the body.
- `grep -Pattern 'executescript|CREATE\s+TEMP|TEMP\s+TABLE'` over `src/` and `scripts/`: only two docstring mentions (`db.py:234`, `db.py:316`); no `executescript`.

### E3 — emit is inert
Fresh DB, `apply_migrations` → `[1,2,3]`, then `emit_reverse_sql(conn, migrations, 3)`:
```
INERT (master+counts+ledger identical): True
```
Returned script (exact):
```
-- XAUUSD Guardian reverse of 0003_signals.sql (version 3).
-- forward sha256: sha256:f4d906d4...
-- down    sha256: sha256:8b5e4263...
-- REVIEW EVERY STATEMENT. This program will not run them.
BEGIN IMMEDIATE;
DROP TABLE main."signals";
DROP TABLE main."signal_runs";
DELETE FROM schema_migrations WHERE version = 3;
DELETE FROM schema_objects WHERE version = 3;
DELETE FROM schema_object_identity WHERE version = 3;
COMMIT;
```
Same result with a temp homonym of `signals` and with an attached `side` database holding its own `signals`: emit returned the script, named only `main.` objects, and left both untouched. (The "0 rows" reading on `main.signals` in that probe is the normal state — 0003 creates empty tables.)

### E4 — script shape
`main`-qualified DROPs; single `BEGIN IMMEDIATE` … `COMMIT`; three ledger deletes; no `temp` / attached schema named; header carries forward and down sha256 plus the review warning. `revert_migration` raised and the database stayed inert in the same probe.

### E5 — completeness
Scratch down file dropping only `signals`:
```
MigrationError: 0003_signals.down.sql leaves objects behind: ['idx_signal_runs_window', 'signal_runs'];
a reverse script must drop every object the migration created, or it is not a reverse.
```
`idx_signals_run` correctly does not count (it vanishes with its table). The real `0003_signals.down.sql` (both tables) emits cleanly.

### E6 — suite, compile, integrity
```
& $py -m pytest -q --junitxml=C:\GS7\review-opt3\junit-opt3.xml -o cache_dir=C:\GS7\review-opt3\pytest-cache
→ exit 0

junit-opt3.xml: tests=297 failures=0 errors=0 skipped=0 time=49.385

& $py -m compileall -q src scripts tests
→ exit 0

manifest before/after: files 240 / 240; added: []; removed: []; changed: []
```

### E7 — spot checks (all refused at emit time)
| Scenario | Result |
|---|---|
| adoption at apply (pre-existing `signals`) | `would adopt existing object(s) ['signals']` |
| FK cascade child `executions(run_id … ON DELETE CASCADE)` | `would drop a table that ['executions -> signal_runs ON DELETE CASCADE'] references` |
| shape drift (`ALTER TABLE signals ADD COLUMN`) | `table 'signals' does not match 0003_signals.sql (declared …)` |
| provenance absent | `no object provenance recorded for migration 3; …` |
| forward file edited after apply | `migration 0003_signals.sql changed after being applied …` |
| same-shape replacement table | `'signals' is not the table that 0003_signals.sql created … Refusing to drop a replacement object.` |

Apply → emit → human-run script → re-apply: remaining tables are only 0001/0002, ledger `[1,2]`, provenance 0/0; re-apply returns `[3]`, ledger `[1,2,3]`, signals tables back.

## 6. CASE A2

Setup: fresh DB, applied `[1,2,3]`; recorded identity equals live identity for all four objects — `(schema rowid, root page, normalised-DDL sha256)`; `schema_version` is recorded but excluded from the ownership comparison (`db.py:226-252`, `276-308`). Operator then dropped `idx_signal_runs_window`, dropped `signals`, recreated it with the exact DDL from `0003_signals.sql`, recreated both indexes in the original order, and inserted one `operator-row-A2`.

- **(a)** `revert_migration(conn, migrations, 3)` → `MigrationError` ("automated reversal has been removed…"); all row counts unchanged; operator row present (1).
- **(b)** `emit_reverse_sql(conn, migrations, 3)` → **returned a script** (drops `main."signals"`, `main."signal_runs"` plus the three ledger deletes); all row counts unchanged; operator row present (1); `apply_migrations` → `[]`; ledger `[1,2,3]`.
- **Final operator row count: 1.**

**Plain answer: the row is safe from the tool.** Neither call writes. It is **not** safe from the emitted script — running it would `DROP TABLE main."signals"` and delete the row. In A2 the library cannot distinguish the replacement from the original (rowid, root page and DDL are reproducible), so the only remaining guard is the human reading `-- REVIEW EVERY STATEMENT. This program will not run them.`

## 7. Residual risk from moving the destructive step to a human

1. **Emit can still recommend a destructive script for an exact-identity replacement** (CASE A2). This is inherent to option 3: the tool can no longer execute, but an operator who runs every emitted script without reading it will lose data the migration did not create. The mitigation is procedural.
2. **FK cascade**: the emit-time refusal covers child tables that exist when the script is emitted. A child created between emit and execution is not covered; running the script then cascade-deletes its rows.
3. **The script is plain text**: nothing binds it to the database it was validated against. Running it against another copy is undetectable.
4. **Unqualified ledger deletes** (W3): a temp homonym can leave the ledger claiming 0003 applied after the tables are gone.
5. **`PRAGMA foreign_keys` is not set by the script**; cascade behaviour at execution depends on the operator's connection settings.

## 8. Review scope and not covered

**Scope:** option 3 as stated in the handoff — remove automated reversal, emit reviewed SQL. Checklist used (no formal acceptance document exists): (1) no executed `DROP`/`DELETE` in library code; (2) emit inert; (3) script shape (`main`, transaction, ledger deletes, no temp/attached names); (4) completeness refusal; (5) A2 behaviour recorded and row survival checked; (6) suite 297 and `compileall`; (7) preconditions still refuse.

**Not covered:**
- `HANDOFF/artifacts/REPORT-F1-OPTION3.md` — absent; searched all of `C:\GS7`. `REPORT-F1-INSPECTION.md` concerns `snap-f1`, not this tree.
- Only `src/guardian/storage/db.py` was read in full for the destructive-path claim; other modules were checked by grep for destructive SQL and `executescript`, not line by line.
- One platform/interpreter only (Windows, CPython 3.11.8, SQLite 3.43.1); no POSIX or Python 3.12+ run.
- No concurrency or crash-injection testing around apply or the emitted script.
- No coverage measurement, mutation testing, or performance profiling.
- The suite's own tests execute emitted scripts through the test-local stand-in; that is test code, not library behaviour, and `src/`/`scripts/` were verified separately to contain no `executescript`.
