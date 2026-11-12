# PHASE 3 — S7 INDEPENDENT REVIEW (Gate S7)

Reviewer: independent Inspector (did not write the code). Read-only review of `C:\GS5\repo`, branch `fix/w1-timezone-validation`.
Date: 2026-11-12. Interpreter: `C:\Python311\python.exe` (Python 3.11.8, pytest 9.2.0). Probes in `C:\GS5\s7-tmp`.

## 1. Conclusion

**Verdict: BLOCK.** One must-fix, in the correctness layer, and it is a destructive-risk finding of exactly the kind S7 rule 5 makes blocking: the 0003 reverse can silently drop a table that 0003 did **not** create. If a database already contains a `signals` table whose column names and order match the forward declaration (for example a pre-S5 prototype with `strength REAL`, `run_id INTEGER`, no primary key), `CREATE TABLE IF NOT EXISTS` adopts it, `apply_migrations` records 0003 as applied anyway, and `revert_migration(..., 3)` then drops it and deletes the ledger row. The legacy rows are gone, no error is raised, and the database afterwards looks as if 0003 had never been applied. I reproduced this end to end (section 2, F1).

Everything else in the S7 checklist reproduces: 267/267 suite green (exit 0), 15/15 reversal tests (exit 0), `compileall` exit 0, the six SHA-256 values in the S6 evidence match the committed tree byte for byte, the sidecar matches, the git chain is linear with no rewrite artefacts, S1/S2/S3/S4 protections exist and pass, S5's commit is intact. Two of my own mutation probes were each killed by exactly one protective test. The S6 design is sound in its main axis (DROP-only whitelist, single transaction, post-condition, hash-pinned forward); it fails only in the adoption case, and the code's own docstring claims that case is guarded.

## 2. Must fix

### F1 — Reverse of 0003 can destroy a pre-0003 table it adopted instead of created

**Location**
- `src/guardian/storage/db.py:286-316` — `_check_declared_shapes` (guards the adoption case by comparing **column names only**: `declared != actual`, lines 309-315).
- `src/guardian/storage/db.py:334-403` — `reversal_plan` accepts the plan because the names match.
- `src/guardian/storage/db.py:405-433` — `revert_migration` executes `DROP TABLE signals`, verifies the objects are gone, then deletes the `schema_migrations` row.
- `src/guardian/storage/db.py:105-147` — `apply_migrations` never checks whether a named object already exists before `executescript`, so 0003 is recorded as applied even when it created nothing.
- Docstring at `db.py:286-297` explicitly claims: *"Guards the `CREATE TABLE IF NOT EXISTS` adoption case: if a table with this name already existed, the forward migration created nothing and recorded itself anyway. Dropping it would then destroy data the migration never owned."* The implementation does not guard that case.

**Problem**
`_declared_columns` returns the nine column *names*; `PRAGMA table_info` returns the live *names*. A pre-existing table with the same nine names in the same order passes, regardless of types, primary key, constraints or semantics. `0003_signals.sql` uses `CREATE TABLE IF NOT EXISTS`, so apply is a silent no-op on that table, yet `schema_migrations` gets a 0003 row. The reverse then drops it as if 0003 owned it. The post-condition (`_verify_reversal`) only checks that the named objects are absent afterwards — which is true precisely because the table was dropped.

**Evidence (executed, not inferred)**
Probe: `C:\GS5\s7-tmp\probe_adoption.py`, run against a copy of the tree at `C:\GS5\s7-tmp\probe` (exit 0):

```
apply 0001+0002 -> [1, 2]
pre-0003 signals rows: 1
pre-0003 signals DDL : CREATE TABLE signals ( symbol TEXT, timeframe TEXT, bar_time_utc TEXT, strategy_id TEXT, direction TEXT, strength REAL, reason_code TEXT, run_id INTEGER, created_utc TEXT)
apply 0003 -> [3]
ledger: [1, 2, 3]
signals DDL after apply (unchanged => adopted): CREATE TABLE signals ( ... strength REAL ... run_id INTEGER ... )
reversal plan tables: ('signal_runs', 'signals') down: 0003_signals.down.sql
revert 0003 -> 3
signals table still exists: False
ledger after revert: [1, 2]
legacy rows surviving: 0 -- table dropped: OperationalError no such table: signals
PRE_0003_DATA_DESTROYED: True
```

The pre-existing table had the same column names/order but `strength REAL`, `run_id INTEGER` and no primary key — the shape a pre-S5 prototype would plausibly have, and precisely the drift the S6 decision D-016 §8 says it refuses. No exception was raised at apply or revert.

**Impact**
Any operator running `revert_migration` against a database that acquired a same-named table outside 0003 loses that table's rows irrecoverably, and the ledger is edited to claim 0003 was never applied. `01_STATE_SNAPSHOT.md` residual R1 records this risk but classifies it non-blocking on the grounds that "data at risk is 0003-era signal data (regenerable); no such DB exists on the official lineage". My probe shows the first half of that rationale is false: the adopted table can be arbitrary legacy data (REAL strengths, INTEGER run ids) that 0003 cannot regenerate. The second half is unverifiable here — the repository contains no SQLite database at all (`Get-ChildItem -Recurse -Include *.sqlite3,*.db,*.sqlite` returned nothing), so "no such DB exists on the official lineage" is an assertion, not a checked fact. The evidence demo's step 6 ("guard refused a reverse that would drop a pre-0003 table") only tests a down file that drops `bars`, a name absent from the forward; it does not exercise adoption, so the demo's "pre-0003 data preserved" conclusion does not cover this path.

**Fix direction**
Record object provenance when the migration is applied: before executing 0003, query `sqlite_master` for each object the forward names and refuse (or record per-object "created_by 0003" rows) when any already exists; then make `reversal_plan` refuse whenever provenance is missing. Comparing full DDL or column types is not sufficient — an adopted table can be byte-identical in shape and still be someone else's data. Add a regression test that seeds an adopted `signals` table, applies, reverts, and asserts the reversal is refused and the rows survive.

## 3. Worth considering

1. **`01_STATE_SNAPSHOT.md` HEAD line is stale in the commit that ships it.** At HEAD `b2057d2`, the snapshot says `HEAD now = f3f6644`; `b2057d2` itself is a later commit that contains that sentence. The same applies to the `origin/...` row. `00_READ_ME_FIRST.md` tells the next agent to compare `git status` and counts against this file, so the first check trips on a clean tree. Suggest making the line relative ("HEAD at snapshot time") and adding `b2057d2` to the chain table.
2. **Status lines still lag reality.** `PHASE3_PLAN.md:3` says "S5 implemented (252/252) ... S6–S7 OPEN" and `PROJECT_STATE.md` still says S6 pending sign-off, while HEAD contains S6 and 267 tests. This is residual R5, already known; it should be fixed in the commit that records the S7 verdict.
3. **`_created_objects` scans comments.** `db.py:196-198` runs `_CREATE_RE` over the raw forward SQL including `--` comments. A comment containing e.g. `CREATE TABLE bars` would add `bars` to the drop whitelist, letting a down file drop a real pre-0003 table and still pass the post-condition. 0003 has no such comment today, so this is latent, but it is the same protection F1 is about. Suggest stripping comments before the scan.
4. **The drift test only covers an added column.** `tests/unit/test_migration_reversal.py:250-261` adds `note TEXT`; no test covers a type-only difference (`strength TEXT` vs `REAL`), which is the shape that passes today and loses data. Covered by the F1 fix, but worth its own test.
5. **Evidence hash-method wording.** The S6 evidence says `HASH_METHOD: SHA-256 over raw file bytes (CRLF preserved)`, but `git ls-files --eol` reports `i/lf w/lf` for the three code files — the checkout is LF on this machine. The hashes themselves match, so this is wording only.

## 4. Only record

- `evidence/phase3-S3-replay-20261105T202217Z.txt` is a committed failed attempt (`ModuleNotFoundError: No module named 'guardian'`); the next file, `...202235Z.txt`, shows `digest_1 == digest_2` over 3141 bars. Noisy but harmless; both are tracked.
- The superseded `phase3-S6-20261109T170723Z.txt` has no "superseded" banner of its own (residual R4); only the snapshot labels it. It is untracked, so a fresh clone does not carry it.
- `compileall` writes only ignored `__pycache__`; `git status --porcelain` was identical before and after (two untracked evidence files only).
- No merge, rebase, graft or replace artefacts: `git replace -l` empty, `git log --merges 9a3b53a..HEAD` empty, every commit in the chain has exactly one parent.
- `HANDOFF/MANIFEST.sha256` verifies 7/7 when evaluated from inside `HANDOFF/`.

## 5. Scope and what I did / did not cover

**Executed (exact commands, from `C:\GS5\repo\ایجنت\xauusd-guardian`)**

| Command | Result |
|---|---|
| `C:\Python311\python.exe -m pytest -o addopts="" -q` | `267 passed in 115.96s`, exit 0 |
| `C:\Python311\python.exe -m pytest tests/unit/test_migration_reversal.py -v` | `15 passed in 5.23s`, exit 0 |
| `C:\Python311\python.exe -m compileall -q src scripts tests` | exit 0 |
| `git rev-parse HEAD` | `b2057d2fe74c3dd4f89a6d3943b51065e6194e52` |
| `git log --oneline -6` | `b2057d2 → f3f6644 → 2e56ae7 → 9a3b53a → 08ce5f3 → bfee6d8` |
| `git status --porcelain` | only two untracked files: `evidence/phase3-S5-20261108T202628Z.txt`, `evidence/phase3-S6-20261109T170723Z.txt` |

**Hashes reproduced** — all six recorded values match both the working file bytes and the HEAD blobs (working tree clean for these paths, `git diff HEAD` empty): `db.py 79e99514…`, `test_migration_reversal.py 20d1617d…`, `0003_signals.down.sql 8b5e4263…`, `DECISIONS_LOG.md f9baa233…`, `PHASE3_PLAN.md 4dfc2a50…`, `PROJECT_STATE.md 481943cf…`. Evidence file `7a6a7f51…` matches its sidecar `44c7dbd6…`.

**Mutation probes (my own, in `C:\GS5\s7-tmp\probe`)**
- M-A: deleted the `_check_declared_shapes(...)` call → `test_revert_refuses_a_drifted_table` FAILED (`DID NOT RAISE MigrationError`), 1 failed / 14 passed.
- M-B: deleted the `_verify_reversal(conn, plan)` call → `test_incomplete_down_script_is_refused_and_rolled_back` FAILED (`DID NOT RAISE MigrationError`), 1 failed / 14 passed.
Both protections are load-bearing.

**Gates judged from code/tests, not prose**
- S1 look-ahead: `tests/unit/test_ema_cross.py:79` truncation property; `tests/unit/test_signal_service.py:143` service-level property. Pass in suite.
- S2 boundary/warmup: `test_ema_cross.py:61` (`ema` returns `None` until warmup), `:67` (no signal before bar 50), `:111` (forming bar refused), `test_signal_service.py:126` (stored forming bar excluded, not trimmed). Pass.
- S3 replay determinism: `test_ema_cross.py:95`; evidence `phase3-S3-replay-20261105T202235Z.txt` digest equality over 3141 bars. Pass.
- S4 MT5 boundary: `tests/security/test_boundaries.py:60`; grep shows `MetaTrader5` reached only via `importlib.import_module` inside `src/guardian/adapters/`. Pass.
- S5 suite: 267 collected, 267 passed, 0 failed/error/skipped.
- S6: forward is `CREATE ... IF NOT EXISTS` only; down is two plain `DROP TABLE`s; reversal in one `BEGIN IMMEDIATE`; whitelist/post-condition/drift checks all present and mutation-tested. **Fails only the adoption case (F1).**

**Not verified**
- `main` = `1dad9588…`: the object exists (`git cat-file -t` → commit) but this clone has no `main` ref (`git show-ref` lists only `fix/w1-timezone-validation` and its origin), so I cannot prove `main` still points there. No fetch was run, per the rules.
- Parallel branch `76d468ed…`: absent from this clone (`git cat-file -t` → exit 128). Cannot verify it is untouched.
- The `_work/ketabkhane-ai-xauusd` snapshot clone cited by the S6 evidence for the `main`/parallel hashes does not exist on this machine, so those two evidence lines cannot be reproduced.
- Fresh-clone check of the two local-only evidence files was not executed; I verified instead that neither name appears in `git ls-tree -r HEAD` and both are untracked, which is equivalent for this purpose.
- No SQLite database exists in the repository, so the "no such DB on the official lineage" claim in R1 could not be checked against real data.
