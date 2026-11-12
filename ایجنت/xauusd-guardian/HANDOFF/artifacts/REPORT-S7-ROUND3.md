# Phase 3 — Gate S7, Round-3 Independent Review

Reviewer: independent inspector (did not write this code)
Date: 2026-11-12
Repository: `C:\GS5\repo\ایجنت\xauusd-guardian`
Branch: `fix/w1-timezone-validation` · HEAD `69e783dbdc3c259f62cb111c2c98c2448867a720`

Command/exit-code shorthand used below: all probe scripts live in `C:\GS5\s7c-tmp` (not deliverables); all suites ran in a bit-identical `robocopy` copy of HEAD at `C:\GS5\s7c-tmp\r3` (`.git` excluded, `PYTHONDONTWRITEBYTECODE=1`) so the repo was never written to.

---

## 1. 结论 — Verdict

**BLOCK.** Three must-fix findings: two executed paths still destroy data 0003 did not create (legacy database written by the pre-fix build; cross-schema `DROP TABLE` through `TEMP`/`ATTACH`), and one path violates the guard's stated contract (quoted / `main.`-qualified DDL is adopted and recorded). The fixes for F1 and F1b are real **for fresh databases** — adoption of `signals` / `SIGNALS` / `Signals` / `sIgNaLs`, and of an identical-shape table, is refused in every variant I tried, and atomic apply survives a hard kill at the ledger boundary. Counts: 必须修 3 · 值得考虑 3 · 仅记录 5.

---

## 2. 必须修 (3)

### M1 — A database written by the pre-fix build still loses adopted rows on revert at HEAD

- **Location:** `src/guardian/storage/db.py:130-136` (version already in ledger -> migration skipped), `db.py:329-365` `_check_declared_shapes` (L346-348 `continue` when the declared table is absent), `db.py:335-341` (docstring asserting the adopted case "cannot reach this check"), `migrations/rollback/0003_signals.down.sql:1-2`.
- **Problem:** the F1 fix only prevents *new* bad records. A database where commit `2e56ae7` (S6) recorded 0003 over a pre-existing `signals` keeps that record forever; `apply_migrations` skips 0003 (it is in history), so the guard is never consulted again. If the adopted table's column names and types match the declaration, `_check_declared_shapes` now *passes*, and `revert_migration(3)` runs `DROP TABLE signals` on data the migration did not create.
- **Impact:** silent, unrecoverable loss of pre-0003 rows for any database created between `9a3b53a` and `3deaf8c`. No error, no warning; the ledger looks healthy afterwards.
- **Evidence (executed):** `C:\Python311\python.exe C:\GS5\s7c-tmp\probe_legacy.py` -> exit 0. Extracted the old module from `2e56ae7` to `C:\GS5\s7c-tmp\oldcode\db_2e56ae7.py` (confirmed `executescript`, no adoption guard), built a DB holding 2 legacy rows in an identical-shape `signals`, recorded 0003, then at HEAD:

```
old apply ledger: [1, 2, 3]   legacy rows: 2
HEAD revert 3 -> 3
signals table still exists: 0
ledger now: [1, 2]
```

  Corroborating text: `db.py:335-341` claims "an adopted table … cannot reach this check"; `HANDOFF/01_STATE_SNAPSHOT.md:90` marks R1 **FIXED** with no legacy-DB caveat; `DECISIONS_LOG.md` D-016 §8 and `PHASE3_PLAN.md` repeat that the ledger "only ever records migrations that created their own objects" — false for these databases.
- **Fix direction:** do not assert an invariant the code cannot check. Add an explicit pre-revert audit for databases whose `schema_migrations` predates the guard (compare each declared object's `sqlite_master.sql` against the declared DDL, refuse on mismatch), and make the release note say plainly that databases created before `69e783d` must be audited or rebuilt. Optionally record the created-object list per migration from now on so future reverts can be verified positively rather than by shape equality.

### M2 — Reversal drops a same-named table in `TEMP` or an `ATTACH`ed schema and still passes its post-condition

- **Location:** `db.py:368-377` `_verify_reversal` (reads `sqlite_master` only), `db.py:346-348` (`continue` when the declared table is missing from `main`), `migrations/rollback/0003_signals.down.sql:1` (unqualified `DROP TABLE signals`).
- **Problem:** SQLite resolves an unqualified `DROP TABLE` against `temp`, then `main`, then attached schemas; when `main.signals` is absent (drift) but `temp.signals` or `aux.signals` exists, the reverse drops that table. `_verify_reversal` then inspects `sqlite_master` — where the table never existed — so it reports success and the ledger is rewritten to `[1, 2]`.
- **Impact:** silent destruction of rows in another schema with a clean exit code; unreachable from code in this repo (no `TEMP`/`ATTACH` usage), reachable from any operator tooling that opens the same connection.
- **Evidence (executed):**
  - `probe_crossschema.py` (exit 0): after `DROP TABLE signals` + `CREATE TEMP TABLE signals` with one row on the same connection -> `REVERT RAN -> 3` / `temp table survives: 0`, ledger `[1, 2]`.
  - `probe_attach2.py` (exit 0): drift + `ATTACH` a db holding `signals` (1 row) -> `revert 3 -> 3` / `aux signals table present: 0`.
  - Raw SQLite semantics confirmed independently (`probe_sqlite_semantics.py`): T2 drops the temp table when both exist; T3 drops the attached table when only attached exists; T4 shows `CREATE TABLE IF NOT EXISTS` still creates in `main` even when `aux` holds the name.
- **Fix direction:** qualify reverse DDL with `main.` and reject schema-qualified statements in the down-script whitelist; have `_verify_reversal` check `sqlite_temp_master` and `PRAGMA database_list` schemas; turn "declared table missing from `main`" into a hard error instead of `continue`.

### M3 — Quoted or `main.`-qualified `CREATE TABLE IF NOT EXISTS` is adopted and recorded (guard contract violated)

- **Location:** `db.py:214-225` `_created_objects` (regex `[A-Za-z_][A-Za-z0-9_]*`, unquoted form only), `db.py:228-240` `_existing_objects`, `db.py:138-144` (the refusal that therefore never fires).
- **Problem:** a forward migration written with `CREATE TABLE IF NOT EXISTS "probe_q"`, `[probe_q2]`, or `main.probe_q3` does not match the parser, so the declared-object set is empty, the adoption check has nothing to compare, and the migration is recorded although it created nothing.
- **Impact:** a false ledger row and a table whose real schema is whatever pre-existed — later writes hit wrong types or fail at runtime. Not destructive by itself: the reverse then refuses (`... not a plain DROP TABLE/INDEX`), i.e. it fails closed.
- **Evidence (executed):** `probe_quoting.py` (exit 0) applied migration 0004 in all three spellings over a pre-existing table -> ledger `[1, 2, 3, 4]` in every case; reversal refused with `0004_probe.down.sql contains a statement that is not a plain DROP TABLE/INDEX: 'DROP TABLE "probe_q"'`. Contradicts the absolute claim in `DECISIONS_LOG.md` D-016 §8, `PHASE3_PLAN.md` (status/gate lines) and `HANDOFF/01_STATE_SNAPSHOT.md:90`.
- **Fix direction:** parse the identifier forms SQLite accepts (double-quoted, `[..]`, backticked, optionally schema-qualified) or fail closed on any `CREATE` the parser cannot attribute to a declared object; add a case to `test_apply_refuses_to_adopt_a_preexisting_table`.

---

## 3. 值得考虑 (3)

- **W1 — `_verify_reversal`'s index half has no test coverage.** `tests/unit/test_migration_reversal.py` (441 lines) kills the table half but not the index half. My mutant `M-C` (`names = plan.tables + plan.indexes` -> `plan.tables`, `C:\GS5\s7c-tmp\mut\`) **survived**: exit 0, 22 passed. Suggest a test that leaves `idx_signals_run` behind and expects failure.
- **W2 — `DECISIONS_LOG.md` D-016 "Effect: 252/252 tests pass" is stale.** Current suite is 274 (executed, exit 0); S5 evidence says 252, pre-F1 267, pre-F1b 270. Suggest pinning the sentence to "252 at time of writing" or updating the number.
- **W3 — `HANDOFF/01_STATE_SNAPSHOT.md:72` advertises an "8-step demo incl. transaction demo".** The demo has 8 steps and no transaction/crash step (apply, revert, re-apply, hostile down, lowercase adoption, `SIGNALS` adoption). Atomicity rests on `test_failed_migration_leaves_no_partial_schema` and my kill probe, not on the demo. Suggest rewording.

---

## 4. 仅记录 (5)

- `HANDOFF/01_STATE_SNAPSHOT.md:11` HEAD cell is vague/self-contradictory (`3deaf8c` "plus round-2 fix"); actual HEAD is `69e783d`.
- `evidence/phase3-S6-20261112T191535Z.txt` header records `HEAD: 3deaf8c` while hashing the uncommitted F1b working tree; all six SHA-256 values match the files at `69e783d`, so the hashes are right but the label is not.
- Evidence `SUMMARY` booleans `s5_commit_unchanged=False`, `S5_IS_HEAD=False`, `S5_PARENT_OK=False` are unlabelled negatives I could not interpret; `9a3b53a` is independently confirmed as an ancestor of HEAD and its cited hash is unreplaced.
- `db.py:147-148` commits the caller's pending transaction before applying (harmless for current callers, surprising for future ones).
- Identifier normalization is duplicated in four functions; the `.lower()` in `_created_objects` is redundant given the lowercasing at every lookup (equivalent mutant, not worth a test).

---

## 5. 审阅范围与未覆盖

**Verified by execution**

| Command (cwd = `C:\GS5\s7c-tmp\r3`, copy of HEAD) | Exit | Result |
|---|---|---|
| `C:\Python311\python.exe -m pytest -q` | 0 | 274 passed (72+72+72+58) |
| `... -m pytest tests/unit/test_migration_reversal.py -v` | 0 | 22 passed in 5.36s |
| `... -m compileall -q src scripts tests` | 0 | clean |
| extracted demo from evidence (7071 bytes), run | 0 | all 8 steps reproduced; steps 1-4 byte-identical to the recorded lines; step 3 `sha256:8b5e4263…aa42`; both adoption refusals identical (`['signals']`, `['SIGNALS']`); `RESULT:` line matches |

**Attacks executed** (all `C:\Python311\python.exe`, exit 0): (a) adopted `signals` with different types -> `would adopt existing object(s) ['signals']`, ledger `[1,2]`, rows intact; (b) `SIGNALS`/`Signals`/`sIgNaLs` identical types -> all refused; (c) identical columns+types, with PK, without PK, with an extra column -> all refused; (d) child process `os._exit(9)` at `INSERT INTO schema_migrations` after `BEGIN IMMEDIATE` + DDL -> reopen: no `probe` table, ledger `[1,2,3]`, `PRAGMA integrity_check = ok`; a `RAISE(ABORT)` trigger on the ledger insert -> `IntegrityError`, no table left; (e) see M1/M2/M3.

**Mutations of my own** (against a copy of the test file under `C:\GS5\s7c-tmp\mut\`): `M-A` adoption guard removed -> killed (4 failures); `M-B` atomic apply reverted to `executescript` -> killed by `test_failed_migration_leaves_no_partial_schema`; `M-C` index-blind `_verify_reversal` -> **survived** (22 passed); `M-D` case-sensitive comparison -> killed by the three case variants.

**Repository state:** `git log --oneline -7` = `69e783d`, `3deaf8c`, `b2057d2`, `f3f6644`, `2e56ae7`, `9a3b53a`, `08ce5f3`; `git rev-list --parents` shows a single-parent linear chain, 5 commits since S5; `git merge-base --is-ancestor 9a3b53a HEAD` exit 0; `git status --porcelain` shows only the two untracked S5/S6 evidence files. Six pinned SHA-256 values re-hashed from the files at HEAD: all match (`8b5e4263…aa42`, `9241c6bd…c248`, `7535759f…3de4`, `36a82fa8…27d1`, `93f46950…25b3`, `625af067…3054`); the sidecar hash `96a05de8…1a1d` matches the evidence file.

**Not covered / could not verify**

- The author's own 8 mutation probes beyond the four I wrote; only my four are evidenced here.
- The meaning of the `s5_* = False` booleans in the evidence `SUMMARY`; I could not reconstruct the generating script, so I verified `9a3b53a` independently instead.
- Operator data directories outside git: there is no `.sqlite3`/`.db`/`.sqlite` file in the project (`data/*.sqlite3` is gitignored), so I could not test a real operator database; M1 is a reconstruction from the pre-fix code at `2e56ae7`.
- `git rev-parse 9a3b53a^{tree}` was mangled by PowerShell argument expansion; tree equality with `08ce5f3` was not captured.
- No test, type check, or probe was run inside `C:\GS5\repo` itself (copies only), by design; the repo was not modified.
