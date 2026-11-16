# Phase 3 — Gate S7, Round-4 Inspection and Remediation

Inspector: independent (did not write the S1–S6 code or the F1/F1b/F1c fixes)
Date: 2026-11-15
Repository: `ایجنت/xauusd-guardian` (clone of `nafeZ1361/ketabkhane-ai-xauusd`)
Branch: `fix/w1-timezone-validation`
HEAD at inspection: `e56b3a69b007e3c797a1a6952e6605d0e787935a`
Tree: `8ad3949e8d331ab70981dc30ce86580785a52907`
Worktree at inspection: clean

Environment: Windows 10 Pro 19045, Python 3.11.8, pytest 9.2.0, SQLite 3.43.1.
Every suite and probe ran on byte-identical copies of the subtree (`C:\GS7\r4`
pre-fix, `C:\GS7\r5` post-fix), hashes verified against the clone; the repository
itself was never written to during inspection.

---

## 1. Verdict

**Round 4 finds all three round-3 must-fix items CLOSED by execution, and two new
defects.** Both new defects were fixed in this round and re-verified. Because the
inspector authored those fixes, this report **does not claim S7 PASS**; a round-5
inspection by a different reviewer is required (rule §6, developer ≠ approver).

| Round-3 finding | Round-4 verdict | Evidence |
|---|---|---|
| **M1** legacy database still loses adopted rows on revert | **CLOSED** — revert now refuses; rows intact | probe B1, B2 |
| **M2** reversal drops a same-named `TEMP`/`ATTACH`ed table | **CLOSED** — drops are `main`-qualified, post-condition spans every schema; foreign rows survive | probe C, D, G, F |
| **M3** quoted / `main.`-qualified `CREATE` adopted and recorded | **CLOSED** for `"name"`, `[name]`, `main.name` | probe E ×3 |
| new **N1** `HANDOFF/MANIFEST.sha256` does not verify for the three S7 reports | **FIXED** — regenerated; 11/11 verify | §3.1 |
| new **N2** backticked identifiers and quoted schema prefixes misparsed | **FIXED** — `_bare_identifier` / `_SCHEMA_PREFIX`; +3 tests | §3.2 |

Suite at HEAD: **279 passed**, exit 0. Suite after the fixes: **282 passed**, exit 0.

---

## 2. Round-3 must-fix items — closure evidence

All probes are `C:\GS7\probes\probe_s7r4.py` (not a deliverable; reproduced under
`evidence/phase3-S7-20261115T171715Z.txt`). Pre-fix run: 12/15 — I, I2 and J fail, all three
attributable to N2. Post-fix run: **15/15, exit 0**.

### M1 — legacy database

**B1** builds a database holding two rows in an identical-shape `signals`, records
0003 in `schema_migrations` with no `schema_objects` row (the `2e56ae7` shape), and
reverts at HEAD:

```
MigrationError: no object provenance recorded for migration 3; this database was
applied before provenance tracking existed, so a safe reverse cannot be derived.
Audit or rebuild the database instead of reverting.
table_exists=1  rows=2  hist=[3]
```

The round-3 reproduction (`HEAD revert 3 -> 3`, `signals table still exists: 0`)
no longer occurs. **B2** covers a database with no `schema_objects` table at all:
`OperationalError: no such table: schema_objects`, `table_exists=1`, `rows=2` —
also refused, but as a raw SQLite error (residual R2).

### M2 — `TEMP` / attached schema

The reverse now issues `DROP {kind} main."{name}"` (db.py:589) and re-inspects every
schema before and after (db.py:483-493).

- **G** — `main.signals` and `temp.signals` both present (the case where SQLite
  resolves an unqualified `DROP` against `temp` first): the reverse **refuses**
  (`left objects behind: ['temp:signals']`) and the temp row survives. Nothing is
  destroyed.
- **C** — drift (no `main.signals`) plus a populated `temp.signals`: refused
  (`no such table: main.signals`), `temp_rows=1`, ledger unchanged.
- **D** — drift plus `ATTACH aux` holding `signals`: refused, `aux_rows=1`.
- **F** — a hostile down-script spelled `DROP TABLE temp.signals;` is rejected
  before execution: `targets schema 'temp'; a reverse may only touch main`.

### M3 — quoted / schema-qualified `CREATE`

Adoption of a pre-existing, different-shape table is now refused for `"probe_q"`,
`[probe_q2]` and `main.probe_q4` — each with
`would adopt existing object(s) [...]` and `hist=[1, 2, 3]`. The backticked spelling
did not fire the adoption message at HEAD but was still rolled back and not recorded
(fail-closed); it is fixed and now reports `would adopt` (§3.2).

### Mutation check of the M2 defence

Removing the `main` qualification (`DROP {kind} "{quoted}"`) in a copy is **killed**
by `tests/unit/test_migration_reversal.py::test_revert_never_targets_a_temp_table`
(`DID NOT RAISE OperationalError` at line 491). The defence is test-protected.
Two unrelated failures in that mutant (`test_boundaries.py`) were caused by the BOM
my mutation script wrote, not by the mutation; the pristine copy is green.

---

## 3. New defects found and fixed

### N1 — the evidence manifest does not verify (must-fix for an evidence gate)

`HANDOFF/MANIFEST.sha256` was last written in `e56b3a6`, the same commit that last
touched the reports it covers, yet three of its ten entries do not match the files
at HEAD under any line-ending or BOM variant:

| File | manifest | actual (LF) |
|---|---|---|
| `artifacts/REPORT-S7.md` | `792a11bc…` | `94ba4a7c…` |
| `artifacts/REPORT-S7-ROUND2.md` | `01f39147…` | `1ff77bbe…` |
| `artifacts/REPORT-S7-ROUND3.md` | `55b8c428…` | `8b8fae5e…` |

The other seven verify once CRLF is normalised (the checkout uses `autocrlf=true`;
the manifest is over LF content). No variant of the three S7 reports matches, so the
pack cannot demonstrate that the reports it ships are the reports that were hashed —
the exact property an S7 evidence gate exists to provide.

**Fix:** `MANIFEST.sha256` regenerated over LF content for every file, including this
report. Verification is now 11/11.

### N2 — identifier parsing contradicts its own contract

`_bare_identifier`'s docstring claims it normalises ``` `name` ```, and `_IDENT`
accepts backticks, but the function never stripped them:

- `CREATE TABLE `probe_bt` (...)` in a clean database was **refused**:
  `did not create declared object(s) ['`probe_bt`']` — a legitimate migration could
  not be applied at all.
- `CREATE TABLE "main".probe_z (...)` parsed as object `"main"`
  (`did not create declared object(s) ['main']`), because `_SCHEMA_PREFIX` accepted
  only a bare schema name.

Both are fail-closed (nothing recorded, nothing destroyed), so neither is
destructive; but the documented contract was false and a whole identifier spelling
was unusable.

**Fix:** `_bare_identifier` now strips a schema prefix before unquoting and accepts
backticks as a quoting character; `_SCHEMA_PREFIX` accepts all four identifier
spellings. Three regression tests added. Post-fix: backticked create applies and is
recorded (`prov=(('table','probe_bt'),)`), backticked adoption is refused with
`would adopt`, and `"main".probe_z` creates `probe_z`.

---

## 4. Residuals (recorded, not fixed)

| # | Residual | Why it does not block |
|---|---|---|
| R1 | `_check_declared_shapes` still `continue`s when a declared table is missing from `main` (db.py:401-402), so the operator sees `OperationalError: no such table: main.signals` rather than a domain error | fail-closed inside the transaction; probe C, D |
| R2 | A database with no `schema_objects` table fails as `OperationalError` instead of `MigrationError` | same refusal, worse message; probe B2 |
| R3 | The post-condition treats *any* same-named owned object in `temp`/attached schemas as "left behind", so a reverse is refused while such an object exists | over-strict, never destructive; probe G |
| R4 | Adoption is compared against `main` only; a same-named object in `temp` does not block an apply (nothing is destroyed — the create lands in `main`) | out of the round-3 scope; no false record |
| R5 | `test_boundaries.py` has no ATTACH coverage and, before this round, no backtick coverage; ATTACH remains untested in-repo (probe D covers it) | test gap, not a code defect |

Round-3's W-items: W1 (index half of `_verify_reversal`) is now covered by
`test_revert_refuses_an_index_left_behind`; W2 (`252/252`) is correctly scoped —
`DECISIONS_LOG.md` says "at the time of S5"; W3 (demo wording) is unchanged and
harmless.

---

## 5. Commands and exit codes

| # | Command (cwd) | Exit | Result |
|---|---|---|---|
| 1 | `python -m pytest -q --junitxml=…` (`C:\GS7\r4`, HEAD) | 0 | tests=279 failures=0 errors=0 skipped=0, 51.6 s |
| 2 | `python -m compileall -q src scripts tests` (`C:\GS7\r4`) | 0 | clean |
| 3 | `python probe_s7r4.py` (`C:\GS7\r4`) | 1 | 12/15 — I, I2, J fail (N2) |
| 4 | `python -m pytest -q` (`C:\GS7\mut1`, `main` qualification removed) | 1 | killed by `test_revert_never_targets_a_temp_table` |
| 5 | `python -m pytest -q --junitxml=…` (`C:\GS7\r5`, post-fix) | 0 | tests=282 failures=0 errors=0 skipped=0, 45.0 s |
| 6 | `python -m compileall -q src scripts tests` (`C:\GS7\r5`) | 0 | clean |
| 7 | `python probe_s7r4.py` (`C:\GS7\r5`) | 0 | **15/15** |
| 8 | manifest verification (`HANDOFF/`) | 0 | 11/11 verify at LF |

Changed files (uncommitted; **no commit and no push were made**):

| File | SHA-256 (worktree / LF) |
|---|---|
| `src/guardian/storage/db.py` | `c3e5133b…c86bf5f` / `93d6de1b…ad32276` |
| `tests/unit/test_migration_reversal.py` | `ab8f56a0…b1f36905` / `e7a2d5ef…9c34483` |

---

## 6. Not covered

- The four author mutation probes from round 3 were not re-run; only the single
  `main`-qualification mutant was repeated here.
- No operator database exists in the repository (`data/*.sqlite3` is gitignored);
  M1/M2 remain reconstructions from the pre-fix code shape, as in round 3.
- Nothing was executed against a live MT5 terminal or a real DEMO account; this gate
  is DEMO-only and does not touch orders.
- Independence: the fixes for N1/N2 are the inspector's own. **S7 remains
  unapproved** until an independent round-5 review passes them.
