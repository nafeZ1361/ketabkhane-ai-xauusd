# F1 Independent Inspection — object ownership remediation (XAUUSD Guardian)

Reviewer: independent (not the author). Read-only. Tree judged: `C:\GS7\snap-f1` (178 files, byte copy).
Interpreter: project venv Python 3.11.8 / sqlite 3.43.1, run with cwd `C:\GS7\snap-f1`, `-B`.
Scratch DBs: `C:\GS7\review-f1\`.

## 1. Verdict

**F1: BLOCK**

The mechanism records `(sqlite_master.rowid, rootpage, sha256(DDL))` per created object and refuses a
reverse when the live triple differs. I reproduced a case where an operator re-creates `signals` with
the migration's own DDL text and *all three fields match the recorded values exactly*; `revert_migration(..., 3)`
then **proceeds**, drops the operator's table and its row, and deletes the version-3 ledger rows.
The deliverable's own guarantee #2 ("a replacement that reuses the definition is still refused whenever its
`sqlite_master` row or root page differs — which is what happens for any table that has indexes") is
therefore false as written: the ids are restored, not refreshed.

## 2. Ownership judgement — what the mechanism does and does not prove

| | |
|---|---|
| **Proves** | The object now sitting in `main` under that name has the same `sqlite_master.rowid`, same `rootpage` and same whitespace-normalised DDL as when the migration committed. In other words: *no drift detectable through these three fields.* |
| **Does not prove** | That the object **is** the one the migration created. All three fields live in the database file, are readable by anyone who can run `SELECT * FROM sqlite_master`, and are therefore reproducible by anyone who can run `CREATE`. |
| **Correct label** | Drift / tamper **detection**. Not ownership. |

**Why the guarantee cannot be established with SQLite and this architecture.** SQLite exposes no stable
object id (the author's own §1), and SQLite keeps no history of a dropped object: after `DROP`, the
original is gone and every surviving signal is a property of the *replacement*, which the operator
controls. Ownership needs evidence the operator cannot fabricate, and any evidence stored inside the
same database file is by definition readable and writable by the operator who has arbitrary SQL on that
file. Under the stated threat model — operator may run arbitrary SQL between apply and revert — an
in-database token cannot distinguish "original" from "faithful re-creation", no matter which fields it
uses. Only evidence held **outside** the database (append-only audit log outside the file, or an HMAC
keyed by a secret the operator cannot read) can. Neither exists here. This is a property of the
architecture, not a bug that a wider tuple would fix.

Note the intermediate finding that matters for the report's reasoning: the naive attack
(`DROP TABLE signals; CREATE TABLE signals <same DDL>`) is refused — but **only because
`sqlite_master.rowid` happened to move 29 → 33**, while `rootpage` was already reused (32 → 32). The
refusal rests on an allocator artefact, not on a principled discriminator. Reorder the operator's
statements and the artefact disappears (CASE A2 below).

## 3. Executed evidence

Driver: `C:\GS7\review-f1\probeA.py`, `probeB.py`, run as

```
Set-Location 'C:\GS7\snap-f1'
& '<venv>\Scripts\python.exe' -B 'C:\GS7\review-f1\probeA.py'
```

Each case starts from a fresh DB, applies 0001–0003 via `apply_migrations`, and prints
`(rowid, rootpage, sql_sha256, schema_version)` recorded vs live for all four version-3 objects.

### 3.1 CASE A — byte-identical DDL, index-free replacement (naive)

```
apply=[1, 2, 3]
  applied   table  signals     rec=(29, 32, 'sha256:2c42e3eb...4a1b', 22) live=(29, 32, ...) equal=True
DROP TABLE main.signals
CREATE TABLE IF NOT EXISTS signals (... exact DDL from migrations/0003_signals.sql ...)
INSERT one operator row
  replaced  table  signals     rec=(29, 32, 'sha256:2c42e3eb...4a1b', 22)
                               live=(33, 32, 'sha256:2c42e3eb...4a1b', 24) equal=False
  replaced  index  idx_signals_run  live=None            (auto-dropped with the table)
  revert(3) -> REFUSED MigrationError: 'signals' is not the table that 0003_signals.sql created: its
               schema rowid, root page or definition changed ... Refusing to drop a replacement object.
  ledger_after=[1, 2, 3]  signals_table=1  signal_runs=1
```

Refused — on `rowid` alone. DDL digest identical, rootpage identical.

### 3.2 CASE A2 — byte-identical, table re-created first in original order → **DEFEAT**

Operator SQL, all of it plain and available:

```
DROP INDEX main.idx_signal_runs_window;
DROP TABLE main.signals;                      -- also drops idx_signals_run
CREATE TABLE IF NOT EXISTS signals (... exact DDL from 0003_signals.sql ...);
CREATE INDEX IF NOT EXISTS idx_signals_run ON signals (run_id);
CREATE INDEX IF NOT EXISTS idx_signal_runs_window ON signal_runs (strategy_id, timeframe, from_utc);
INSERT INTO signals VALUES ('XAUUSD','M5','2026-01-01T00:00:00Z','s1','LONG','1.0','rc','operator-row-A2','...');
```

```
  replaced  table  signals                rec=(29, 32, 'sha256:2c42e3eb...4a1b') live=(29, 32, 'sha256:2c42e3eb...4a1b')
  replaced  table  signal_runs            rec=(27, 30, 'sha256:015831dc...') live=(27, 30, 'sha256:015831dc...')
  replaced  index  idx_signals_run        rec=(31, 34, 'sha256:4fc48c14...') live=(31, 34, 'sha256:4fc48c14...')
  replaced  index  idx_signal_runs_window rec=(32, 35, 'sha256:1ca4a73e...') live=(32, 35, 'sha256:1ca4a73e...')
  revert(3) -> PROCEEDED, returned 3
  ledger_after=[1, 2]  signals_table=0
  signals=n/a no such table: main.signals        <-- operator row destroyed
```

Every field of every owned object matches. The reverse deletes a table the migration did not create and
with it the operator's row, then removes ledger rows 3 / schema_objects 3 / identity 3.

This is the requirement violation stated in the brief: *"the tool must not delete objects it did not create."*

### 3.3 CASE A3 — the shipped regression test's own sequence

`tests/unit/test_migration_reversal.py:799-814` does `DROP TABLE signals; DROP TABLE signal_runs;
executescript(0003)` and asserts refusal.

```
  testseq  table  signals                rec=(29,32,...) live=(29,32,...)
  testseq  table  signal_runs            rec=(27,30,...) live=(27,30,...)
  testseq  index  idx_signals_run        rec=(31,34,...) live=(31,35,...)   <-- root pages swapped
  testseq  index  idx_signal_runs_window rec=(32,35,...) live=(32,34,...)   <-- root pages swapped
  revert(3) -> MigrationError: 'idx_signal_runs_window' is not the index that 0003_signals.sql created ...
```

The test passes, but not for the reason its docstring gives. Docstring: *"Same DDL, same page, same
rowid: only schema_version can distinguish it."* Measured: all four rowids **are** identical, the pages
are not — the two index root pages swapped 34↔35. The test is green on a freelist coin-flip; CASE A2 is
the same idea with one statement reordered and it fails open. The test therefore asserts a guarantee it
does not exercise.

### 3.4 CASE B — same nine columns, different DDL (the originally reported F1 attack)

```
  replaced  table  signals  live=(33, 32, 'sha256:fe3a29bc...', 24)  rec=(29, 32, 'sha256:2c42e3eb...', 22)
  revert(3) -> REFUSED MigrationError: 'signals' is not the table that 0003_signals.sql created ...
  ledger_after=[1, 2, 3]  signals_table=1  signals_rows=1
```

The reported F1 attack is still refused, the replacement and its row survive, the ledger stays
`[1,2,3]`, `signal_runs` is untouched. Refusal is structurally before any DROP: `_check_object_identity`
runs inside `reversal_plan` (`db.py:759`), and `revert_migration` calls `reversal_plan` before
`BEGIN IMMEDIATE` (`db.py:786-792`), so no DROP statement has executed when it raises.

## 4. Object-attached marker assessment

Proposal: attach something to the table at apply time (trigger or index) so `DROP TABLE` destroys the
marker and a replacement lacks it.

- **Created atomically with the table?** Yes, achievable: `apply_migrations` runs the migration statements
  and the bookkeeping inserts inside one `BEGIN IMMEDIATE ... COMMIT` (`db.py:420-453`), so a marker created
  there commits or rolls back with the table.
- **Does DROP remove it?** Yes. Measured in CASE A: immediately after `DROP TABLE main.signals`, live
  identity for `idx_signals_run` is `None` — the index dies with the table, and SQLite drops table triggers
  the same way. The "dies with the table" property is real.
- **Can a replacement reproduce it?** Yes, trivially. In CASE A2 the operator re-created both indexes
  verbatim and got back the *exact* original ids (31/34, 32/35). A marker's definition is visible in
  `sqlite_master.sql` before the drop and in `migrations/0003_signals.sql` afterwards. A marker defeats an
  operator who does not know it exists; it does not defeat one who does.
- **Schema/runtime cost.** Measured against this codebase, not estimated:
  `_OBJECT_TYPES` (`db.py:58`) includes `trigger` and `view`, and `_verify_reversal` (`db.py:641-652`) treats
  any non-owned object that disappears as *"removed objects it did not own"* and any owned object that
  survives as *"left objects behind"*. A trigger marker dropped along with its table therefore trips the
  `lost` branch on **every legitimate revert** unless the marker is first added to `owned` — i.e. recorded
  as provenance, which collides with the rule that provenance records only objects the migration declared.
  An index marker avoids that branch but is a real B-tree: write cost on every `signals` insert, and it must
  be excluded from `_check_declared_shapes` / `_checked_down_statements`.
- **Conflict with the declared-objects rule?** Yes, as soon as the marker is recorded. If instead it is left
  unrecorded, it is an undeclared object that db.py creates — the exact category `_unattributed_create`
  (`db.py:312-328`) refuses in migration SQL.

**Recommendation: reject** — as an ownership proof. It moves the same defect one layer down: the marker is
readable and copyable by the same operator, while costing a schema object per table, insert-path overhead,
and a conflict with the declared-objects rule. It would be worth revisiting only if re-scoped to tamper
*evidence* and authenticated with a secret held outside the database — at which point the secret, not the
marker, is doing the work.

## 5. Also verified

**Suite (counts from JUnit XML, not dots).**

```
python -m pytest -q --junitxml=C:\GS7\review-f1\junit.xml   (cwd C:\GS7\snap-f1)
testsuite 'pytest' errors=0 failures=0 skipped=0 tests=295 time=37.860
python -m compileall -q src scripts tests  -> exit 0
```

295 matches the claim.

**Lifecycle.** `apply=[1,2,3]`, `revert=3`, `reapply=[3]`, `revert=3`, third revert →
`MigrationError: migration 3 is not applied`, ledger `[1,2]`. Round-trip and the repeated-reversal refusal
both behave as claimed.

**Atomicity on failure.** `DROP TABLE main.signals` with the table already absent → the identity check
passes it through (`got is None: continue`, `db.py:301-303`), the `DROP` fails inside the transaction, and
the rollback is complete: `ledger=[1,2,3]`, `signal_runs` present, 4 identity rows for v3 still present.
Atomic. The error surfaces as a raw `sqlite3.OperationalError: no such table: main.signals` rather than a
`MigrationError` — see §7.

**F2 — same-named object in `temp` / attached schema.**

```
F2a CREATE TEMP TABLE signals (x TEXT)
    revert(3) -> MigrationError: reversal of 3 left objects behind: ['temp:signals']
    ledger=[1,2,3] main_signals=1 temp_signals=1 signal_runs=1
F2b ATTACH ... AS side; side.signals exists
    revert(3) -> MigrationError: reversal of 3 left objects behind: ['side:signals']
    ledger=[1,2,3] main_signals=1 signal_runs=1
```

Confirmed. Mechanism: `_verify_reversal` (`db.py:648-652`) scans **every** schema from `_schema_list`, so a
name that merely collides in `temp`/attached blocks the commit. Safety impact: fail-closed, transaction
rolled back, nothing deleted, nothing lost — but a legitimate revert is refused and the message ("left
objects behind") is factually wrong, since the reversal left nothing behind. Recoverable by dropping,
renaming, or detaching the colliding object.
**Classification: ADVISORY.**

**F3 — DDL text inside a string literal attributed as a declared object.**

```
fixture C:\GS7\review-f1\mig-f3b\0004_probe_sl.sql:
  CREATE TABLE probe_sl (id TEXT);
  CREATE INDEX idx_probe_sl ON probe_sl (id);
  INSERT INTO probe_sl (id) VALUES ('CREATE TABLE ghost');

_created_objects(...) = {'probe_sl': 'table', 'idx_probe_sl': 'index', 'ghost': 'table'}
apply -> MigrationError: migration 0004_probe_sl.sql did not create declared object(s) ['ghost']; refusing to record it
ledger=[1,2,3]  probe_sl_present=0
```

Confirmed: the literal is parsed as a declaration (`_created_objects`, `db.py:169-180`, regex over the whole
text, no literal awareness) and the migration is refused. Impact: a legitimate migration whose data
contains SQL text cannot be applied; a confusing message names a table that appears nowhere in the DDL.
It fails closed and does **not** widen the reverse whitelist — reverse ownership comes from measured
`provenance` (`db.py:478-483`), not from this parse — so there is no deletion-safety consequence.
**Classification: ADVISORY.**

**Hashes.** Both claimed digests match, byte for byte:

```
src\guardian\storage\db.py                 D836DA1BE944C472851075983731B6A92D5303F1E1F59A21890C53C9C46118F6
tests\unit\test_migration_reversal.py      3C5BD94B4A0CB92FA5A7D5934399E75FEEC776CAC61FD5D73146DB1E7815CCFF
```

(The claimed `db.py` digest is `d836da1b…18f6` and the test digest `3c5bd94b…ccff`; both confirmed.)

## 6. Must fix

**M1 — the triple is reproducible; the ownership claim does not hold.**
Location: `src/guardian/storage/db.py:270-309` (`_check_object_identity`, comparison at `:304`), and the
claim it supports in `HANDOFF/artifacts/REPORT-F1-REMEDIATION.md` §2 "Guarantees" items 1–2.
Problem: `(schema_rowid, rootpage, sql_sha256)` are all database-resident, operator-writable properties. A
re-creation performed in the original order restores all three for all four version-3 objects.
Impact: `revert_migration(conn, migrations, 3)` deletes a table and row it did not create and removes the
ledger rows for version 3 — the precise outcome the mechanism was introduced to prevent. Anyone who reads
`REPORT-F1-REMEDIATION.md` §2 will believe index-bearing tables are covered; CASE A2 shows they are not.
Basis: CASE A2 output above; `REPORT-F1-REMEDIATION.md` §2 item 2 ("still refused whenever its
`sqlite_master` row or root page differs — which is what happens for any table that has indexes").
Fix direction: withdraw the ownership claim and re-scope the mechanism as drift detection (rename the
guarantee, say plainly what it detects); if the threat model genuinely requires "must not delete objects
it did not create" against an operator with SQL access, move the evidence out of the database — append-only
audit log outside the file, or an HMAC keyed by a secret the operator cannot read — and treat an absent or
unverifiable token as fatal rather than as `continue`. Do not widen the tuple; the next field is equally
reproducible.

**M2 — the regression test asserts a guarantee it does not exercise.**
Location: `tests/unit/test_migration_reversal.py:799-814`.
Problem: the docstring claims "Same DDL, same page, same rowid: only schema_version can distinguish it"
(the contradiction is visible in the first output of CASE A3: all rowids match). The refusal actually comes
from the two index root pages swapping 34↔35 — an allocation accident. The test therefore stays green while
the real defeat (CASE A2, one statement reordered) is untested.
Impact: false assurance for exactly the property under review; the next reader will treat F1 as closed.
Basis: CASE A3 vs CASE A2 outputs.
Fix direction: make the test assert what the mechanism actually guarantees (drift detection), and add the
ordered re-creation sequence as an explicit known-limitation test that documents the current outcome, so the
limitation cannot silently change.

## 7. Worth considering

- `src/guardian/storage/db.py:276-282` — docstring says a reverse "proceeds only when every signal still
  matches", which reads as an ownership proof. It matches the code but not the guarantee. Say what it
  detects.
- `src/guardian/storage/db.py:795` — a missing owned table reaches `DROP` and surfaces as a raw
  `sqlite3.OperationalError`, not `MigrationError`; every other refusal in this module is a `MigrationError`.
  Callers that catch `MigrationError` will let this one through.
- `src/guardian/storage/db.py:648-652` — F2's message "left objects behind" misdiagnoses the cause (a
  pre-existing homonym, not a leftover). Naming the schema and saying the object pre-existed would save the
  operator a wrong first fix.
- `src/guardian/storage/db.py:354-363` — `schema_version` is stored and never used in the decision (by
  design, §2). Recording a column that is deliberately ignored invites a future reader to start trusting it.

## 8. Not covered / limitations of this inspection

- `HANDOFF/artifacts/REPORT-S7-ROUND8.md` is **not in the snapshot** (verified: `HANDOFF/artifacts` holds
  S6, S7, ROUND2–ROUND7, no ROUND8). Any claim depending on it is unverified. The F1 report I did read was
  `REPORT-F1-REMEDIATION.md`.
- I did not re-run the author's own probes (`probe_f1.py`, `probe_s7r4.py`, `probe_round5_cases.py`,
  `probe_round7.py`) or the claimed 9/9, 15/15, 7/7, 7/7 counts; my evidence is the independent drivers in
  `C:\GS7\review-f1\`, not theirs.
- `evidence/phase3-F1-20261115T192506Z.txt` and its `.sha256` sidecar, plus the manifest verification
  (16/16) in §7 of the report, were not checked.
- Only migration 3's reverse path was attacked. Migrations 1 and 2 have no down files in the snapshot
  (`migrations/rollback` holds only `0003_signals.down.sql`), so their reverse path is untested here.
- I tested two re-creation orderings, not an exhaustive search of freelist outcomes. CASE A2 is sufficient
  to refute the guarantee; I make no claim about which ordering an operator would find first.
- No hostile-SQL sandbox, WAL/rollback-journal edge cases, or concurrent-writer interleavings were examined.
