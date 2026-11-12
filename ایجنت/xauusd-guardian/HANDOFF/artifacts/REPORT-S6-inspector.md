# Inspector Report — Stage S6, `xauusd-guardian`

Reviewer: independent Inspector (read-only). Date: 2026-11-09.
Scope: S6 acceptance requirement "Migration 0003 must be additive and reversible."
Baseline used for judgement: that requirement plus the sub-criteria enumerated in the task brief
(applies to current schema, correct bookkeeping, pre-0003 data survives, signals/signal_runs as planned,
reversal explicitly demonstrated, re-application deterministic and lossless, no destructive operation on
pre-existing schema/data, tests green, evidence reproducible, no unrelated files changed).

**VERDICT: PASS**

## 1. 结论 (Conclusion)

PASS. No must-fix findings. All 10 working-tree paths are inside S6 scope; the S5 commit is untouched.
`0003_signals.sql` is additive (three `CREATE ... IF NOT EXISTS` statements, no ALTER/DROP of 0001/0002),
its reverse lives in `migrations/rollback/0003_signals.down.sql`, and `revert_migration` drops only objects
parsed from the paired forward file, inside one `BEGIN IMMEDIATE ... COMMIT`, with a post-condition that
forces rollback of a partial reverse. I re-ran, independently: 15/15 targeted tests, 267/267 full suite,
`compileall`, a full apply -> seed -> revert -> re-apply lifecycle probe against a real SQLite file, and two
of my own mutation controls in a throwaway copy. One residual, documented gap remains (adoption of an
identically shaped pre-existing `signals` table is not refused on revert), but it matches the authoritative
decision record D-016 and the plan, is unreachable on the supported 0003-as-creator path, and does not
violate the additive/reversible requirement for this repository's schema.

## 2. 必须修 (Must fix)

None (0 findings).

## 3. 值得考虑 (Worth considering)

### W1. Identical-shape "adoption" is not refused — a reverse can drop a table 0003 did not create
- Location: `src/guardian/storage/db.py:286-315` (`_check_declared_shapes`), docstring lines 294-296;
  reached from `reversal_plan` at `db.py:391`; executed by `revert_migration` at `db.py:405-435`.
- Problem: the guard compares only column *names* — `declared = _declared_columns(forward_sql, table)`
  (line 305) vs `PRAGMA table_info` (line 310). If a table named `signals` already existed with exactly the
  declared column list, `0003_signals.sql`'s `CREATE TABLE IF NOT EXISTS` created nothing, the ledger still
  records 0003 applied (`db.py:138-143`), and `revert_migration` later drops that table and its rows.
- Executed evidence: `C:\GS5\inspector-tmp\probe_adoption.py` (run from copy
  `C:\GS5\inspector-tmp\s6-copy-20261109T2110Z`) pre-created `signals`/`signal_runs` with the exact live DDL
  plus one signal row, with no ledger row; `apply_migrations` -> `[3]`; `revert_migration` returned 3 and
  `signals present = False`, ledger `[1, 2]`. Output: "before apply: signals rows = 1 / revert SUCCEEDED /
  after revert: signals present = False".
- Conflict: the function docstring (db.py:294-296) claims it "Guards the CREATE TABLE IF NOT EXISTS adoption
  case ... Dropping it would then destroy data the migration never owned" — it does not. The authoritative
  records do *not* overclaim: D-016 item 8 says only "each such table's live columns still match the declared
  ones", and `PHASE3_PLAN.md:42` says "may not drop a table whose live shape drifted". Behaviour matches the
  spec; the docstring is the outlier.
- Impact: a database where `signals` was created outside 0003 (hand-applied DDL, prototype, or a lost
  `schema_migrations` row) loses that table and its rows on revert. Data at risk is 0003-era signal data,
  regenerable from bars, and no such database exists on the official lineage; hence not a blocker.
- Fix direction: either narrow the docstring to what is actually checked, or add a provenance check (e.g.
  refuse to revert when the table pre-dates the ledger row / when a non-empty `signals` table's rows are not
  attributable to a recorded `signal_runs.run_id`). Do not edit `0003_signals.sql` — its hash is pinned at
  `db.py:130-135` and `db.py:364-369`; a stricter forward rule belongs in a new migration.

### W2. `0003_signals.sql` header comment is now false, and cannot be corrected in place
- Location: `migrations/0003_signals.sql:4-11`.
- Problem: it states the reverse "is deliberately NOT implemented" and that a `0003_*_down*.sql` file would be
  "applied as the next forward step". Both are untrue after S6: `migrations/rollback/0003_signals.down.sql`
  exists and executes, and the dotted name cannot match the forward discovery pattern
  (`^[0-9]{4}_[a-z0-9_]+\.sql$`; verified by `discover_migrations` returning exactly
  `0001_init.sql, 0002_market_data.sql, 0003_signals.sql` in `test_down_file_is_never_discovered_as_a_forward_migration`).
- Impact: a future reader of the forward file is told the opposite of the implemented state; the file is
  hash-pinned, so an editor would break `reversal_plan` and `apply_migrations` for every applied database.
- Fix direction: leave the file byte-identical; rely on D-016 item 8 ("The earlier statement that reversal was
  a manual DROP TABLE IF EXISTS step is superseded") and add a one-line pointer in the down file's header
  (already partially present at `migrations/rollback/0003_signals.down.sql:1-9`).

### W3. Superseded evidence file is still hash-inconsistent with the tree
- Location: `evidence/phase3-S6-20261109T170723Z.txt`.
- Problem: its recorded hashes for `db.py` (`dc278fae...`), the test file (`57d256...`), `DECISIONS_LOG.md`
  (`af9a53...`) and `PHASE3_PLAN.md` (`7c2d9e...`) do not match the current files; only `PROJECT_STATE.md`
  and the down file match. It also records 8 targeted tests / 260 suite. The authoritative file
  `evidence/phase3-S6-20261109T173019Z.txt` explicitly labels the earlier one "earlier attempt, not the code
  under test".
- Impact: an auditor who picks the wrong file will conclude the evidence does not reproduce. Low risk because
  the supersession note exists, but the stale file carries no banner of its own.
- Fix direction: add a `SUPERSEDED BY ...` first line to 170723Z (or move it under `evidence/superseded/`).

### W4. Plan status line contradicts the S6 gate line
- Location: `PHASE3_PLAN.md:3` ("S5 implemented (252/252 suite green) ... S6–S7 OPEN") vs `PHASE3_PLAN.md:50`
  ("**S6 candidate** — reversibility implemented in code and exercised by tests; awaiting independent
  Inspector sign-off"), and the measured suite is 267 tests.
- Impact: the top-of-file status understates S6 progress; a reader stopping at line 3 would not know S6 exists.
- Fix direction: update line 3 in the same edit that records the S6 verdict.

### W5. Mutation-probe source is not reproducible from the evidence
- Location: `evidence/phase3-S6-20261109T173019Z.txt` mutation section (records command, SHA-256
  `639357b3...` of `C:\GS5\mutation_probe.py`, and M1–M4 results, but not the script body). The demo script
  `C:\GS5\s6_demo.py` *is* embedded in the same evidence file (lines 105-124 output verified byte-identical).
- Impact: M1–M4 can be checked for result but not regenerated; only the hash ties them to a script that lives
  outside the repository.
- Fix direction: embed the mutation probe source in the evidence file, or place both helper scripts under
  `evidence/` (outside `migrations/`, so `discover_migrations` is unaffected).

## 4. 仅记录 (Notes only)

- `apply_migrations` calls `conn.executescript(sql)` (db.py:138) before the ledger INSERT/commit (db.py:139-143); a crash in that window is the realistic route to an unrecorded-but-created table, i.e. the W1 adoption shape.
- `_verify_reversal` (db.py:318-331) asserts only that the planned object names are gone from `sqlite_master`; pre-0003 row survival is asserted by the tests' before/after snapshot (`test_migration_reversal.py:44-49, 92`), not by production code.
- Changed paths (10): M `DECISIONS_LOG.md`, M `PHASE3_PLAN.md`, M `PROJECT_STATE.md`, M `src/guardian/storage/db.py` (+324); ?? `evidence/phase3-S5-20261108T202628Z.txt` (S5 leftover), ?? two S6 evidence files, ?? `evidence/phase3-S6-20261109T173019Z.txt.sha256`, ?? `migrations/rollback/`, ?? `tests/unit/test_migration_reversal.py`. All in S6 scope; no unrelated tracked file changed.
- Down file uses plain `DROP TABLE` without `IF EXISTS` by design (`migrations/rollback/0003_signals.down.sql:3-5`), so a missing table fails inside the transaction rather than recording a reversal that did not occur.
- Evidence 173019Z `.sha256` = `7a6a7f51...`, matching the evidence file's own hash; all six S6 file hashes it records match the files on disk now.

## 5. 审阅范围与未覆盖 (Coverage and gaps)

Verified against the working tree, not against the author's claims:
- Repository safety: branch `fix/w1-timezone-validation`; HEAD `9a3b53af95267c6ecaeca6b567006f671786ecd7`; parent `08ce5f331a72d5b13c5757654e098ac397ba9d1b`; `packed-refs` origin ref `08ce5f3`; reflog top is the S5 commit (2026-11-09 00:38:24 +0330); HEAD/parent/status re-checked unchanged after all probes. No git write/remote command was run by me.
- Baseline: snapshot clone `_work\ketabkhane-ai-xauusd` has `main = 1dad9588083f210fca868f49358aff44826e6f2f`.
- Implementation read in full: `db.py` `apply_migrations` (105-146), `discover_down_migrations` (90-102), `_created_objects`, `_split_sql_statements`, `_checked_down_statements` (248-283), `_check_declared_shapes` (286-315), `_verify_reversal` (318-331), `reversal_plan` (334-402), `revert_migration` (405-435); whole down file; whole 317-line test file.
- Schema vs plan: `0003_signals.sql:13-46` matches `PHASE3_PLAN.md:37-38` column-for-column; `strength` is `TEXT` as required by D-016 item 2.
- Executed by me from `C:\GS5\repo\ایجنت\xauusd-guardian` with `C:\Python311\python.exe`:
  - `-m pytest tests/unit/test_migration_reversal.py -v` -> 15 passed, exit 0, 2.53s.
  - `-m pytest -q` -> exit 0; JUnit `C:\GS5\inspector-tmp\s6-full-junit.xml` tests=267 failures=0 errors=0 skipped=0.
  - `-m compileall -q src scripts tests` -> exit 0.
  - `C:\GS5\s6_demo.py` -> exit 0; output byte-identical to evidence 173019Z lines 105-124 (bars=2, feed_runs=2, plan sha256 `8b5e42...`, guard refuses `DROP bars`).
  - `probe_lifecycle.py`: apply 1+2, seed bars/feed_runs, apply 3 -> ledger [1,2,3], filename `0003_signals.sql`, sha256 `sha256:f4d906d4...` equal to file bytes, UTC `applied_at`, tables/indexes present; revert -> objects gone, pre-0003 schema and row counts/content identical, ledger [1,2]; re-apply -> [3], same sha256, new `applied_at`, schema identical (`probe_reapply_diff.py`: no diffs), second apply -> `[]`.
  - `probe_adoption.py`: result quoted in W1.
  - Mutation controls in copy `s6-copy-20261109T2110Z`: M1 disable the `_check_declared_shapes` call -> exactly `test_revert_refuses_a_drifted_table` FAILED (DID NOT RAISE), 14 passed, exit 1. M2 replace `_checked_down_statements(...)` with raw `_split_sql_statements(...)` -> 2 FAILED (`test_down_script_may_only_drop_objects_the_forward_created`, `test_down_script_rejects_anything_that_is_not_a_plain_drop`), showing `DROP TABLE bars` would otherwise execute. Copy `db.py` restored to repo hash `79e99514...`.

Not covered / limits:
- Evidence entries M3 (transaction removed) and M4 (shape check removed) were not re-executed by me; the provided `mutation_probe.py` writes to `C:\GS5\mut`, outside the mandated `C:\GS5\inspector-tmp`, so I used my own M1/M2 instead. Their recorded results are consistent with my M1.
- `evidence/phase3-S6-20261109T170723Z.txt` was compared by hash only, not re-derived.
- No real production/live database was available; all lifecycle and adoption tests ran on fresh SQLite files under `C:\GS5\inspector-tmp`.
- MetaTrader5 was never imported or contacted; no order path touched.
- I did not verify the 15 evidence-listed node IDs individually; I confirmed the same file collects 15 items and that a fresh run of that file yields 15 passed.