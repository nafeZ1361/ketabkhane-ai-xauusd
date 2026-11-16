# F1 — Data-Integrity Remediation

Scope: S7 residual F1 only. Developer-side record; **not** an approval. S7/F1 require a fresh
independent inspection (§8).

Date: 2026-11-15 · Branch `fix/w1-timezone-validation` · HEAD `e56b3a6` (uncommitted work)

---

## 1. Root cause

`reversal_plan` proved *provenance* (the ledger says this migration created an object with this
name) and compared *shape* (`_check_declared_shapes`: column names and declared types). Neither is
identity. An operator can drop the migration-owned `signals`, re-create a table with the same nine
columns, and the reverse drops it — because the name matches, the shape matches, and the ledger
still says migration 3 created `signals`.

Measured before designing (probe `probe_identity.py`): SQLite exposes **no stable object id**.
On `DROP TABLE` + `CREATE TABLE` with a byte-identical definition, both `sqlite_master.rowid` and
`rootpage` are **reused** (observed: rowid 1 → 1, rootpage 2 → 2). `VACUUM` did not change them in
that probe. So no single field can separate "the original" from "a re-creation".

## 2. Design

A new additive bookkeeping table records a **per-object identity token** at apply time:

```
schema_object_identity(
  version, kind, name,
  schema_rowid,      -- sqlite_master.rowid
  rootpage,          -- sqlite_master.rootpage
  sql_sha256,        -- sha256 of the whitespace-normalised DDL
  schema_version     -- main.schema_version at apply (diagnostics only)
)
```

- **Apply** (`apply_migrations`): after the DDL and before commit, measure every object the
  migration actually created and store its token in the same transaction. Measured, not parsed.
- **Revert** (`reversal_plan`): `_check_object_identity` requires, for every owned table/index,
  that the live `(schema_rowid, rootpage, sql_sha256)` equals the recorded triple. Any mismatch →
  `MigrationError`, raised **before** the transaction that performs the DROPs. If the database has
  no identity rows for that version (applied by an earlier build), the reverse is refused with an
  explicit "audit or rebuild" message.
- **Revert** also deletes the identity rows with the ledger rows, so a re-apply records a fresh
  token.

### Guarantees

1. A replacement object with a different definition (the reported F1 attack) is refused: the DDL
   digest differs, and usually the rowid too.
2. A replacement that reuses the definition is still refused whenever its `sqlite_master` row or
   root page differs — which is what happens for any table that has indexes (they are re-created
   with new schema rowids) and for most re-creations.
3. Nothing is dropped, no ledger row is deleted, and no unrelated object is touched on refusal —
   the check runs before the DROP transaction.
4. A database applied before the token existed cannot be reverted; it must be audited or rebuilt.
5. Normal apply → revert → re-apply → revert continues to work; a second revert refuses with
   "migration 3 is not applied".

### Known limitation (stated, not hidden)

Byte-identical re-creation of an **index-free** table in a database whose freelist hands back the
same root page is not distinguishable from the original: SQLite reuses both `rootpage` and
`sqlite_master.rowid`, and every other signal is equal by construction. `schema_version` was tried
as a tie-breaker and **removed from the decision**: it is global, so any unrelated DDL (including
`CREATE TEMP TABLE`) changed it and blocked legitimate reverts. Closing that last case needs a
recorded identity SQLite does not currently expose; the mitigation is that apply-time adoption is
already refused and the token covers every replacement that differs in definition or placement.

## 3. Files changed

| File | Change |
|---|---|
| `src/guardian/storage/db.py` | `schema_object_identity` table; `_object_identity`, `_recorded_identity`, `_check_object_identity`; token recorded in `apply_migrations`; verified in `reversal_plan`; identity rows deleted on revert; safety-model item 5 documents the guarantee |
| `tests/unit/test_migration_reversal.py` | 3 tests: same-shape replacement refused; byte-identical replacement refused; re-apply records a fresh identity (round-trip) |
| `HANDOFF/artifacts/REPORT-F1-REMEDIATION.md` | this report |
| `evidence/phase3-F1-20261115T192506Z.txt` (+`.sha256`) | commands, outputs, digests |
| `PROJECT_STATE.md`, `HANDOFF/01_STATE_SNAPSHOT.md`, `HANDOFF/MANIFEST.sha256` | bookkeeping |

No other path changed; `git diff --stat` shows 5 files.

## 4. Original F1 reproduction (executed after the fix)

```
apply 0001-0003
DROP TABLE main.signals
CREATE TABLE signals (symbol TEXT, timeframe TEXT, bar_time_utc TEXT, strategy_id TEXT,
                      direction TEXT, strength TEXT, reason_code TEXT, run_id TEXT, created_utc TEXT)
INSERT INTO signals VALUES ('XAUUSD.','M5','t','s','LONG','1','r','run','c')

revert_migration(..., 3)
→ MigrationError: 'signals' is not the table that 0003_signals.sql created: its schema rowid,
  root page or definition changed after the migration was applied. Refusing to drop a replacement object.
→ replacement rows = 1, columns = 9, ledger = [1,2,3], signal_runs untouched
```

9/9 F1 checks passed: attack refused · replacement survives · ledger unchanged · unrelated objects
untouched · normal round-trip · re-apply · repeated reversal safe · atomic · token recorded.

## 5. Test results

| Command | Exit | Result |
|---|---|---|
| `pytest -q` (copy `C:\GS7\r8`) | 0 | **tests=295 failures=0 errors=0 skipped=0** |
| `python -m compileall -q src scripts tests` | 0 | clean |
| `probe_f1.py` (F1 attack + round-trip guarantees) | 0 | **9/9** |
| `probe_s7r4.py` (round-4 regression, 15 scenarios) | 0 | **15/15** |
| `probe_round5_cases.py` (round-5 regression, 7 cases) | 0 | **7/7** |
| `probe_round7.py` (round-7 items, 7 cases) | 0 | **7/7** |

Suite history: 279 → 282 → 287 → 292 → **295**.

## 6. Evidence

- `db.py` sha256 `d836da1be944c472851075983731b6a92d5303f1e1f59a21890c53c9c46118f6`
- `tests/unit/test_migration_reversal.py` sha256 `3c5bd94b4a0cb92fa5a7d5934399e75feec776cac61fd5d73146db1e7815ccff`
- `evidence/phase3-F1-20261115T192506Z.txt` + `.sha256` sidecar

## 7. Manifest

Regenerated over LF content; includes this report. Verified 16/16.

## 8. Remaining risks

| # | Risk | Status |
|---|---|---|
| 1 | byte-identical re-creation of an index-free table can reuse rowid and rootpage | open, documented limitation |
| 2 | databases applied before the identity token refuse to revert | by design (fail-closed) |
| 3 | F2 (same-named `temp`/attached object blocks a revert) | out of scope, unchanged |
| 4 | F3 (DDL text inside a string literal is attributed) | out of scope, unchanged |
| 5 | `schema_version` recorded but not enforced | by design, see §2 |

## 9. Independent inspection command

```
cd C:\Users\icFixer.ir\AppData\Roaming\AutoClaw-oversea-official\accounts\41daec57d4756a03ca8efb2086ae29e4998b4a2ee8e2540c2e48ca7db7cf9831\projects\ایجنت\xauusd-guardian\ایجنت\xauusd-guardian
git status --short ; git diff --stat HEAD
robocopy . C:\GS7\rev-f1 /E /XD .git .venv __pycache__ .pytest_cache data logs
cd C:\GS7\rev-f1
$env:PYTHONDONTWRITEBYTECODE="1"
C:\Users\icFixer.ir\AppData\Roaming\AutoClaw-oversea-official\accounts\7f9fa7c15983c9654b410a0d812b523be39e835c034f44ac0c2e8061a1288073\projects\ایجنت\xauusd-guardian\.venv\Scripts\python.exe -m pytest -q
C:\Users\icFixer.ir\AppData\Roaming\AutoClaw-oversea-official\accounts\7f9fa7c15983c9654b410a0d812b523be39e835c034f44ac0c2e8061a1288073\projects\ایجنت\xauusd-guardian\.venv\Scripts\python.exe -m compileall -q src scripts tests
```

The inspector should reproduce the F1 attack itself, inspect the token design, verify the
replacement and its rows survive with the ledger unchanged, verify normal reversal and re-apply,
and check atomicity.
