# Phase 3 — Gate S7, Round 5: Remediation Record

Author: the inspector who ran round 4 (not the S1–S6 author)
Date: 2026-11-15
Applies to: `HANDOFF/artifacts/REPORT-S7-ROUND5.md` (independent round-5 review, verdict BLOCK)

This is a **developer-side** record, not an approval. Round 5 found three must-fix
defects and one worth-considering item. All four are closed below. **S7 is still not
PASS**: an independent round-6 review of these changes is required.

---

## 1. What round 5 found

| ID | Defect | Class |
|---|---|---|
| MF1 | `apply_migrations` records a migration that created nothing (`CREATE TABLE /*c*/ IF NOT EXISTS …` over an existing table, `SELECT 1;`, `CREATE TEMP TABLE …`) — both guards become vacuous when the parser attributes nothing | false ledger row, M3 class |
| MF2 | `_declared_shape` kept the pre-fix regex, so a backticked / quoted-schema / comment-separated `CREATE` applies and is recorded but can never be reverted | apply/revert asymmetry |
| MF3 | `revert_migration` deletes rows in tables it never created through `ON DELETE CASCADE` (SQLite's implicit `DELETE` on `DROP TABLE` with `foreign_keys=ON`), exit 0, clean ledger | silent data loss |
| W2 | `DROP TABLE "temp"."signals"` skipped the schema check because quoted names were excluded, then executed as `main."signals"` | guard bypass (benign in effect, wrong in principle) |

## 2. What changed (`src/guardian/storage/db.py`)

1. **MF1a — block comments.** `_strip_comments` now removes `/* … */` as well as `--`.
   Without this, `CREATE TABLE /*c*/ IF NOT EXISTS x` never matched `_CREATE_RE`, so
   `declared` was empty and both the adoption guard and the `missing` guard had nothing
   to compare.
2. **MF1b — a migration must create something.** Inside the apply transaction, after
   measuring `created` from `sqlite_master`, an empty `created` now raises
   `MigrationError("… created no objects in main; refusing to record a migration that
   changed nothing …")`. This closes the data-only and `TEMP`-only cases in one branch.
   Data-only migrations are therefore **out of scope** for this project and say so in
   the error.
3. **MF2 — one identifier dialect.** `_declared_shape` now builds its pattern from
   `_SCHEMA_PREFIX` and accepts `"x"`, `[x]`, `` `x` `` and `schema.x`; it searches the
   comment-stripped text and slices the *same* string (mixing the two offset spaces was
   a defect in the first attempt at this fix, caught by the suite).
4. **MF3 — cascade pre-flight.** `_check_foreign_key_dependents` walks every non-owned
   table in `main`, reads `PRAGMA main.foreign_key_list`, and refuses the reverse if any
   of them references an owned table with `ON DELETE CASCADE` / `SET NULL`, naming the
   child and the action. It runs in `reversal_plan`, so the refusal is reviewable before
   anything is dropped.
5. **W2 — quoted schema prefixes.** The down-file schema test now parses the prefix with
   the same identifier rules, so `"temp"`, `` `temp` `` and `[temp]` are rejected exactly
   like `temp`.

Five regression tests added (287 total): no-op refusal, block-comment adoption,
backtick round-trip (apply **and** revert), cascade refusal, quoted-schema down-file.

## 3. Verification (executed)

| Command | Exit | Result |
|---|---|---|
| `pytest -q` (copy `C:\GS7\r6`) | 0 | **287 passed**, 0 failed, 0 error, 0 skipped |
| `python -m compileall -q src scripts tests` | 0 | clean |
| `probe_s7r4.py` (the 15 round-4 scenarios) | 0 | **15/15**, no regression |
| `probe_round5_cases.py` (round-5 repros) | 0 | **7/7** |

Round-5 reproduction cases, after the fixes:

```
C1  CREATE TABLE /*c*/ IF NOT EXISTS probe_c (over an existing table)
    -> MigrationError: would adopt existing object(s) ['probe_c']            hist=[1,2,3]
C1b SELECT 1;
    -> MigrationError: created no objects in main; changed nothing           hist=[1,2,3]
C1c CREATE TEMP TABLE probe_tmp
    -> MigrationError: created no objects in main; changed nothing           hist=[1,2,3]
C2  operator_child REFERENCES signal_runs ON DELETE CASCADE
    -> MigrationError: … ON DELETE CASCADE/SET NULL …                       child_rows=1, hist=[1,2,3]
C3  CREATE TABLE `probe_bt`  -> apply [4], shape (('id','TEXT'),), revert 4, table gone
C6  declared shapes: plain/backtick/quoted-schema/block-after-TABLE/line-comment all (('id','TEXT'),)
W2  DROP TABLE "temp"."signals"
    -> MigrationError: targets schema 'temp'; a reverse may only touch main   hist=[1,2,3]
```

## 4. Residuals after this round

| # | Residual | Status |
|---|---|---|
| R1 | a missing `main` table surfaces as `OperationalError` at DROP time | open, accepted (fail-closed) |
| R2 | a database without `schema_objects` fails as `OperationalError` | open, accepted (fail-closed) |
| R3 | a same-named object in `temp` makes the post-condition refuse | open, accepted (over-strict, never destructive) |
| R6→ | shape equality is treated as provenance: a same-shape replacement table would still be dropped (round-5 W1) | **open** — needs a recorded identity token (`rootpage` + SQL hash); out of scope for this round |
| R11 | data-only migrations are impossible by design now | accepted, documented in the error message |
| R12 | `HANDOFF/MANIFEST.sha256` does not cover `evidence/` | open, accepted |

## 5. Status

S7 remains **unapproved**. Nothing was committed or pushed; the whole change set is in
the working tree. Round 6 must re-execute MF1, MF2, MF3 and W2 independently and must
not rely on this document.
