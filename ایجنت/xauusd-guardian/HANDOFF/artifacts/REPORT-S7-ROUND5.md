# S7 Gate — Round 5 Independent Inspection Report

| Field | Value |
|---|---|
| Gate | S7 (migration apply/reverse safety), round 5 |
| Inspector | independent reviewer; did not write the code, the fixes, or the round-4 report |
| Date | 2026-11-15 |
| Tree under review | `xauusd-guardian/ایجنت/xauusd-guardian` (nested worktree) |
| Branch / HEAD | `fix/w1-timezone-validation` / `e56b3a69b007e3c797a1a6952e6605d0e787935a` |
| Working-tree delta | 5 modified + 3 untracked paths, no commit, no push (verified with `git status --short`) |
| Working copy used for execution | `C:\GS7\rev5` (robocopy of the worktree, excludes `.git/.venv/__pycache__/data`); `db.py` byte-identical to the worktree |
| Baseline copy | `C:\GS7\headtree` (copy of `rev5` with `db.py` and `test_migration_reversal.py` replaced by the committed HEAD blobs) |
| Runtime | Python 3.11.8, pytest 9.2.0, SQLite 3.43.1, Windows 10 19045 |
| **VERDICT** | **BLOCK — 3 must-fix findings** |

---

## 1. Verdict

**BLOCK.** The manifest fix (N1) and every suite claim hold exactly as reported, and round-3 M1/M2 stay closed under every spelling I could construct. But three defects are demonstrated by execution against the current tree:

1. `apply_migrations` still **records a migration that created nothing**, and can still **adopt a pre-existing table with a foreign schema** — the fail-closed half of round-3 M3 was never implemented; only the regex was widened.
2. The N2 fix was applied to the **apply** path only. `_declared_shape` still carries the pre-fix regex, so a backticked, quoted-schema or comment-separated `CREATE` **applies and is recorded but can never be reverted** — the round's own test asserts only the apply half.
3. `revert_migration` **silently deletes rows in tables it did not create** through `ON DELETE CASCADE`, exits 0, and leaves a clean ledger. The post-condition compares object inventories, never rows.

All three are in the correctness layer and all three are cheap to close; none is a documentation or style matter.

### 1.1 Round-4 claim → verdict

| # | Round-4 claim | Verdict | What I executed |
|---|---|---|---|
| 1 | M1, M2, M3 are closed | **PARTIAL — M3 still open** | M1: legacy DB (no `schema_objects`; empty provenance; partial provenance) refuses with `MigrationError` and leaves rows/history untouched. M2: `temp.signals` shadowing, `main`-drift with populated `temp`/attached tables, hostile `DROP TABLE temp.signals` all refuse; drops are rebuilt as `main."<name>"`. M3: fails — see MF1 (`CREATE TABLE /*c*/ IF NOT EXISTS` over an existing table is adopted and recorded). |
| 2 | N2 fixed: `_bare_identifier` strips backticks, `_SCHEMA_PREFIX` accepts quoted/bracketed/backticked prefixes | **PARTIAL — apply path only** | Parser now attributes all four spellings (`plain`, backtick, `"main".`, `` `main`. ``, `[x]`, mixed case, dotted quoted names) and adoption is refused for each of the 11 spellings I tried. But `_declared_shape` was not updated: backticked / quoted-schema / comment-separated declarations revert-refuse forever — see MF2. |
| 3 | N1 fixed: `HANDOFF/MANIFEST.sha256` verifies 11/11 over LF | **VERIFIED** | `python C:\GS7\review5\manifest_check.py` → `entries: 11`, `real -> ok=11 bad=0 missing=0`, `unlisted: [] \| listed-but-absent: []`. Staleness is caught: one byte flipped in `00_READ_ME_FIRST.md` → `ok=10 bad=1`; deleting `artifacts/REPORT-S7.md` → `missing=1`. The manifest is not vacuous. |
| 4 | Suite 282 passed, exit 0; `compileall` exit 0 | **VERIFIED** | `pytest -q` in `C:\GS7\rev5` → junit `tests=282 failures=0 errors=0 skipped=0 time=58.152`, exit 0; zero `skipped`/`xfail` elements in the XML. `python -m compileall -q src scripts tests` → exit 0. |
| 5 | No assertion weakened; remaining 279 tests untouched | **VERIFIED** | `git diff --numstat HEAD -- tests` → `43 0 tests/unit/test_migration_reversal.py` (additions only, single file). `git diff --stat HEAD -- src` → `db.py 7 +5 -`, nothing else. HEAD baseline in `C:\GS7\headtree` → `tests=279 failures=0 errors=0 skipped=0`, so 282 = 279 + exactly 3. The 3 new tests fail on HEAD `db.py` (`did not create declared object(s) ['main']`) and pass on the tree — they bind the fix, they are not vacuous. |
| 6 | No destructive path survives: cannot make `revert_migration` drop/lose a table it did not create, nor `apply_migrations` record a migration that created nothing | **FALSIFIED (both clauses)** | Record-what-it-did-not-create: C1 (below), also `SELECT 1;` and `CREATE TEMP TABLE` both recorded with empty provenance. Silent loss: C2 deletes rows of an operator table through `ON DELETE CASCADE`, exit 0. Drop-what-it-did-not-create: C7 drops a same-shape replacement table (worth-considering W1, needs operator DDL). |

---

## 2. Must-fix (3)

All line numbers refer to `C:\GS7\rev5\src\guardian\storage\db.py`, byte-identical to `src/guardian/storage/db.py` in the worktree. All findings were executed, not inferred.

### MF1 — `apply_migrations` records a migration that created nothing, and still adopts a foreign schema

- **Position:** `db.py:269-300` (`declared = _created_objects(sql)` at 269, adoption guard 271-276, `missing` guard 287-292, ledger + provenance insert 293-300). Invariant stated in the function's own docstring at `db.py:243-246`.
- **Problem:** `declared` is produced by a regex (`_created_objects`, `db.py:159-170`) over `_strip_comments`, which strips `--` only (`db.py:117-119`). Any `CREATE` the regex cannot attribute yields `declared = {}`, which makes *both* guards vacuous — the adoption check iterates an empty tuple, and `missing = set() - created` is empty. The migration then commits a ledger row with the measured `created` set, which is also empty. `created` being empty is never rejected, so "nothing happened" is recorded as success — the exact clause the docstring promises.
- **Impact:** the ledger claims the migration applied while the object under that name is whatever pre-existed, with a different schema. Code written against the declaration fails at runtime (`no such column`), and the database cannot be walked back: the empty provenance makes `reversal_plan` refuse at `db.py:529-534` with a message about "a database applied before provenance tracking existed", which is false. This is round-3 M3's impact class, unfixed. Same outcome for a data-only migration and for `CREATE TEMP TABLE` (nothing lands in `main`, yet it is recorded).
- **Basis (round-3 M3 fix direction):** "fail closed on any CREATE the parser cannot attribute"; the round-4 report claims this class is closed. The code instead widens the regex and leaves the empty-set path open. `db.py:396-398` also asserts "Adoption cannot reach this check" — C1 disproves it.
- **Evidence (executed):**

  ```
  cd C:\GS7\rev5 ; $env:PYTHONPATH="C:\GS7\rev5\src" ; python C:\GS7\review5\repro_r5.py
  == C1  forward: CREATE TABLE /*c*/ IF NOT EXISTS probe_c  ; probe_c already exists ==
    apply 1-3      -> ([1, 2, 3], None)
    declared       -> {}
    apply 0004     -> applied=[4] err=None
    recorded prov4 -> ()
    history        -> [1, 2, 3, 4]
    probe_c cols   -> [('other', 'TEXT')] rows= 1
    revert 4       -> (None, 'MigrationError: no object provenance recorded for migration 4; this database was applied before provenance tracking existed, ...')
  ```

  `probe_c` keeps its pre-existing column `other`; the declared `id TEXT NOT NULL` was never created; the ledger says 4 is applied; the reverse is refused with a false explanation. Companion cases from the same run family: `SELECT 1;` → `recorded=True prov4=()`; `CREATE TEMP TABLE probe_tmp` → `recorded=True prov4=()`.
- **Fix direction:** inside the apply transaction, after measuring `created`, refuse when `created` is empty (a migration that changed nothing in `main` must not be recorded) — this closes C1, the data-only case and the TEMP case in one branch. Optionally also refuse when `_strip_comments(sql)` contains `CREATE` but `declared` is empty, so the error names the unattributable statement instead of the generic "changed nothing". Decide explicitly whether data-only migrations are in scope; if they are, give them their own recorded kind rather than an empty provenance.

### MF2 — the N2 fix was not applied to `_declared_shape`: a recorded migration can be impossible to revert

- **Position:** `db.py:339-346` (`_declared_shape` regex still `(?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)?` / `(?:"t"|\[?t\]?)`); consumed by `_check_declared_shapes` at `db.py:405-409`.
- **Problem:** `_created_objects`/`_bare_identifier` were widened to accept backticks and quoted schema prefixes, but `_declared_shape` was left at the pre-fix pattern and has no backtick branch, no quoted-schema branch, and no comment handling. For those spellings it returns `()`, and `_check_declared_shapes` converts that into `declares no columns … refusing to drop an unverifiable table`.
- **Impact:** apply accepts the declaration and records correct provenance; revert refuses permanently. The migration is stuck at "applied, unrevertable" — discovered at rollback time, in an incident, with a message that misstates the cause (the file plainly does declare columns). The round's own new test `test_apply_accepts_a_backticked_declaration` asserts only the apply half, so the asymmetry is invisible to the suite. This is the same defect class the round claims to close ("a whole identifier spelling was unusable"), moved from apply to revert rather than removed.
- **Basis:** round-4 §3: "`_bare_identifier` now strips a schema prefix before unquoting and accepts backticks as a quoting character; `_SCHEMA_PREFIX` accepts all four identifier spellings … a whole identifier spelling was unusable". After the fix that spelling is usable to apply and unusable to reverse.
- **Evidence (executed):**

  ```
  == C3  forward: CREATE TABLE `probe_bt` ; down: DROP TABLE probe_bt ==
    apply 0004     -> applied=[4] err=None prov4=(('table', 'probe_bt'),)
    _declared_shape(probe_bt) -> ()
    revert 4       -> (None, "MigrationError: 0004_probe.sql declares no columns for 'probe_bt'; refusing to drop an unverifiable table")
    history        -> [1, 2, 3, 4] probe_bt present = True

  == C6  _created_objects / _declared_shape on the spellings ==
    plain              created={'probe_c': 'table'} declared_shape=(('id', 'TEXT'),)
    backtick           created={'probe_c': 'table'} declared_shape=()
    quoted-schema      created={'probe_c': 'table'} declared_shape=()
    block-after-TABLE  created={} declared_shape=()
    block-after-IFNE   created={'if': 'table'} declared_shape=()
    line-comment       created={'probe_c': 'table'} declared_shape=()
  ```

  Same asymmetry reproduced for `CREATE TABLE "main".probe_qs` and for `CREATE TABLE /*c*/ IF NOT EXISTS …` on a clean database (each applies and records, then refuses to revert).
- **Fix direction:** build `_declared_shape`'s pattern from the same `_SCHEMA_PREFIX` + `_IDENT` constants (plus a backtick branch in the name alternative) and strip `/* */` alongside `--`; then add one round-trip test per spelling (apply → revert → object gone) rather than an apply-only assertion, so the pair can never diverge again.

### MF3 — `revert_migration` deletes rows in tables it did not create (FK cascade), silently

- **Position:** `db.py:589-591` (drops) and `db.py:475-495` (`_verify_reversal`, object inventories only); `connect()` sets `PRAGMA foreign_keys = ON` at `db.py:84`, so cascade is the default behaviour.
- **Problem:** dropping an owned table with `DROP TABLE main."<name>"` fires `ON DELETE CASCADE` on every FK referencing it and deletes those rows. `_verify_reversal` compares `(type, name)` inventories before/after, so row loss is invisible; the transaction commits, `revert_migration` returns the version, and nothing is logged.
- **Impact:** operator or derived tables that reference an owned table lose rows with a clean exit code and a clean ledger. `revert_migration` is exactly the operation a human runs when they want to undo one migration, and the tool reports success while destroying data it was never authorised to touch. A plausible DEMO schema (`executions(run_id REFERENCES signal_runs(run_id) ON DELETE CASCADE)`) loses its audit rows on `revert_migration(3)`.
- **Basis:** round-3 M2 established that silent destruction of rows outside the migration's own objects is must-fix, whatever the exit code; claim 6 says no such path survives.
- **Evidence (executed):**

  ```
  == C2  operator_child(run_ref REFERENCES signal_runs(run_id) ON DELETE CASCADE), then revert 3 ==
    apply 1-3      -> ([1, 2, 3], None)
    child rows before revert -> 1
    revert 3       -> reverted=3 err=None
    child rows after revert  -> 0
    history        -> [1, 2]
  ```

- **Fix direction:** before the drops, pre-flight every `main` table with `PRAGMA main.foreign_key_list(<t>)`; if any non-owned table references an owned table with `ON DELETE CASCADE` or `SET NULL`, refuse with a `MigrationError` naming the child table and the action. Surface the affected row counts so the operator can decide. Toggling `PRAGMA foreign_keys=OFF` is the alternative, but it must run outside the transaction (it is a no-op inside one) and would leave dangling child rows — if chosen, that trade-off needs to be stated in the docstring.

---

## 3. Worth considering (4)

### W1 — shape equality is treated as provenance; a same-shape replacement is dropped
- **Position:** `db.py:388-421` (`_check_declared_shapes`), `db.py:528-537` (provenance by name).
- **Problem:** provenance records a bare name. If the owned table is dropped and re-created with the declared shape between apply and revert, `_check_declared_shapes` passes and `revert_migration` drops the replacement.
- **Evidence (executed):** C7 — `DROP TABLE signals`, re-create from `0003_signals.sql`, insert 1 row, `revert 3` → `reverted=3 err=None`, `signals present after -> False`, `history [1, 2]`.
- **Suggestion:** SQLite has no stable object identity, so a complete fix needs a recorded token (e.g. `sqlite_master.rootpage` + normalised `sql` hash at apply time, accept spurious refusals after `VACUUM`). Minimum viable: report the row count about to be dropped and require an explicit confirmation for tables whose recorded token does not match.

### W2 — down-file schema check is bypassed by a quoted prefix, then rewritten to `main`
- **Position:** `db.py:452` — `if "." in raw_name and not raw_name.startswith('"'):`.
- **Problem:** `DROP TABLE "temp"."signals"` skips the schema test entirely, passes the ownership check after `_bare_identifier` strips the prefix, and is then executed as `DROP TABLE main."signals"` (`db.py:589-591`). The statement's stated schema is silently rewritten; the error text "a reverse may only touch main" is enforced only for unquoted names.
- **Evidence (executed):** B5/E3-02 family — `DROP TABLE "temp"."signals"; DROP TABLE "main"."signal_runs";` → `result=3`, history `[1,2]`; and C5 shows the benign `DROP TABLE "main"."signals"` form works as intended.
- **Suggestion:** parse the prefix with `_SCHEMA_PREFIX` and compare it whatever the quoting, so quoted and unquoted spellings get the same verdict.

### W3 — round-4 §5 "Changed files" table is incomplete
- **Position:** `HANDOFF/artifacts/REPORT-S7-ROUND4.md:170-175` lists 2 paths.
- **Problem:** `git status --short` shows 5 modified paths plus 3 untracked. The table omits `HANDOFF/MANIFEST.sha256` (which §3.1 says was regenerated), `HANDOFF/01_STATE_SNAPSHOT.md` (`+16/−7`) and `PROJECT_STATE.md` (`+16/−2`).
- **Impact:** the change set cannot be reconstructed from the report of record; a release engineer replaying it would miss the printed-artifact updates and the manifest.
- **Suggestion:** list all five modified paths plus the untracked report/evidence files, or state "see `git status --short`" and paste it.

### W4 — the round-4 evidence artifact is UTF-16LE and reads as binary
- **Position:** `evidence/phase3-S7-20261115T171715Z.txt` (untracked).
- **Problem:** the file is UTF-16LE with a BOM; `Get-Content`, `grep` and `git diff` see NUL-interleaved bytes, so the "authoritative" evidence for round 4 cannot be searched or diffed, and the manifest does not cover it.
- **Suggestion:** write evidence logs as UTF-8 (no BOM) and add them to the manifest, or keep them out of the gate record.

---

## 4. Record only

- Round-4 residual R1 confirmed (`_check_declared_shapes` `continue` on a missing table → `OperationalError: no such table: main.signals` at DROP time); fail-closed, poor message.
- Round-4 residual R2 confirmed (DB without `schema_objects` → `OperationalError` instead of `MigrationError`).
- Round-4 residual R3 confirmed (a same-named object in `temp` makes the post-condition refuse; over-strict, never destructive).
- Round-4 residual R5 confirmed (no in-repo ATTACH or block-comment coverage).
- `_check_declared_shapes` docstring (`db.py:396-398`) states "Adoption cannot reach this check"; C1 shows it can — folded into MF1.
- Suite wall time differs between runs (58.2 s here vs 45.0 s in round 4): environment, not a finding.
- Round 4 was both fixer and reviewer of N1/N2 (self-declared at `REPORT-S7-ROUND4.md:187-188`); this round's independence is why it is re-executed from scratch.
- Untracked `HANDOFF/artifacts/REPORT-S7-ROUND4.md`, `evidence/*.txt`, and the modified `MANIFEST.sha256` mean the printed record is not reproducible from HEAD alone.

---

## 5. Review scope and not covered

**Standards applied.** Round-3's report defines the review standard and the M1/M2/M3 must-fix set; round-4's six claims are the acceptance surface for this round; findings are triaged as must-fix / worth considering / record-only under the inherited rubric (must-fix = wrong result, violated explicit requirement, security risk, or real-use failure).

**Claims checked by execution (not by reading the round-4 report):**
- Claim 1: 3 legacy-DB cases (no `schema_objects`, empty provenance, partial provenance), 4 schema-collision cases (`temp` shadowing, drift with populated `temp`, drift with an attached DB, hostile `DROP TABLE temp.signals`), 11 adoption spellings, and the down-file `main`-qualification rebuild.
- Claim 2: parser probes over plain / backtick / bracket / `"main".` / `` `main`. `` / `MAIN` / `"MAIN"` / dotted quoted names / spaced prefixes / `CREATE UNIQUE INDEX`, plus `_created_objects` and `_declared_shape` directly.
- Claim 3: independent re-implementation of the manifest check over LF content, plus deliberate mutation and deletion of listed files to prove staleness is caught.
- Claim 4: full suite on the post-fix copy and on a HEAD-baseline copy, junit parsed for skip/xfail, plus `compileall`.
- Claim 5: `git diff` against HEAD for `src` and `tests`, and the 3 new tests executed against HEAD `db.py` to prove they fail there.
- Claim 6: 6 new minimal repro cases (`C:\GS7\review5\repro_r5.py`, output at `C:\GS7\review5\repro_r5.out.txt`), each in a fresh database built from the repo's own migrations.

**Reproduction commands.**
```
cd C:\GS7\rev5
$env:PYTHONDONTWRITEBYTECODE="1"; $env:PYTHONPATH="C:\GS7\rev5\src"
python -m pytest -q --junitxml=C:\GS7\review5\junit-r5.xml
python -m compileall -q src scripts tests
python C:\GS7\review5\repro_r5.py
python C:\GS7\review5\manifest_check.py
```

**Not covered.**
- No operator production database exists in the repo (`data/*.sqlite3` is gitignored); every case is reconstructed from the repo's migrations plus synthetic operator DDL. The frequency of the MF1/MF2 spellings in real migrations is a project-history question I cannot answer from this tree.
- Round-4 residual R4 (adoption compared against `main` only, so a same-named `temp` object does not block an apply) was not re-tested; I did not try to construct a case where it matters.
- The round-3 mutation probes were not re-run; I ran only the HEAD-vs-tree test comparison and the 3 new tests against HEAD.
- No MT5 terminal, DEMO account, broker credentials, orders, or live trading were touched; this gate is DEMO-only and the review was read-only on the repository (no commit, push, amend, reset, checkout or clean).
- Windows path/MAX_PATH behaviour, WAL recovery after a crash mid-revert, and concurrent writers were not exercised.
- I did not review `xauusd_research` at the git toplevel; the nested worktree is the tree under review.