# PHASE 3 / GATE S7 — ROUND-2 RE-REVIEW (after BLOCK)

- Date: 2026-11-12
- Reviewer: independent Inspector, round 2, read-only
- Subject: `fix/w1-timezone-validation` @ `3deaf8c`, project `ایجنت/xauusd-guardian`
- Interpreter: `C:\Python311\python.exe` (3.11.8, pytest 9.2.0), sqlite3 3.43.1
- **VERDICT: BLOCK** — 1 must-fix. The original F1 attack is closed, but the same destruction is still reachable through identifier case, silently.

---

## 1. Repository state as reviewed

```
branch : fix/w1-timezone-validation
HEAD   : 3deaf8ce7b1bc5abc20f795d7caf32b6fb24170e
```

`git log --oneline -6`:

```
3deaf8c fix(s6): refuse adoption of pre-existing objects; record S7 finding F1
b2057d2 docs(handoff): record S6 and handoff commits, remote sync
f3f6644 docs(handoff): agent handoff pack for S7 and beyond
2e56ae7 feat(s6): reversible migration 0003 with guarded reversal
9a3b53a feat(signals): complete Phase 3 S5 signal service
08ce5f3 docs: sync project state with Phase 2 and W1 acceptance
```

`git status --porcelain` — no tracked modification, two pre-existing untracked evidence files:

```
?? ".../xauusd-guardian/evidence/phase3-S5-20261108T202628Z.txt"
?? ".../xauusd-guardian/evidence/phase3-S6-20261109T170723Z.txt"
```

Linearity — `git rev-list --parents -n 6` gives one parent per commit: `3deaf8c -> b2057d2 -> f3f6644 -> 2e56ae7 -> 9a3b53a -> 08ce5f3`. Matches the prescribed chain, no merge commit.

`9a3b53a` intact: `git cat-file -p 9a3b53a` → tree `8644d18...`, parent `08ce5f3...`, author == committer timestamp; `git diff --name-status 9a3b53a^ 9a3b53a` → exactly the 12-file S5 set listed in the evidence (lines 41-55). Unamended as far as repository data can show (an amend would have changed the SHA itself).

The F1 fix commit contains only the claimed delta (db.py +58, test_migration_reversal.py +79, three doc files, handoff pack, evidence, REPORT-S7.md). Diff reviewed line by line; nothing unrelated.

---

## 2. The blocking question (item 2): is legacy data still destructible?

Probe: `C:\GS5\s7b-tmp\probe2.py`, exit 0, full transcript `C:\GS5\s7b-tmp\probe2.log`. It imports `guardian.storage.db` from the repo read-only and builds every database under `C:\GS5\s7b-tmp`.

### Case A — the exact original F1 attack: CLOSED

Database at 0001+0002, pre-existing `signals` with the same nine column names and **different types** (`strength REAL`, `run_id INTEGER`, no PK), one legacy row.

```
1 apply 0001+0002 -> [1, 2]
2 apply_migrations refused: MigrationError: migration 0003_signals.sql would adopt existing
  object(s) ['signals'] instead of creating them; refusing to record a migration that creates
  nothing. Resolve the database manually, then re-run.
3 ledger: [1, 2] | legacy rows: 1 | signal_runs? False
4 revert refused: MigrationError: migration 3 is not applied
5 after revert attempt: ledger: [1, 2] | legacy rows: 1
```

The original attack no longer applies and no longer reverts. Confirmed independently of the author's report.

### Case B — same attack, table named `SIGNALS` / `Signals` / `sIgNaLs`: OPEN, data destroyed silently

Same setup, one capital letter different in the table name:

```
=== SIGNALS / DIFFERENT types (REAL,INTEGER) ===
  1 apply 0001+0002 -> [1, 2]
  2 apply_migrations -> APPLIED (guard miss): [3]
  3 ledger: [1, 2, 3] | legacy rows: 1 | signal_runs? True
  4 revert_migration(3) -> REVERTED WITHOUT ERROR
  5 AFTER: ledger: [1, 2] | legacy rows: TABLE GONE
```

Identical result for `Signals`, and for all three names with **matching** TEXT types. No error is raised at any point; the legacy rows are gone and the ledger row is deleted.

Mechanism, verified against sqlite3 3.43.1 (`C:\GS5\s7b-tmp\probe_case.py`):

| operation | semantics | consequence in db.py |
|---|---|---|
| `SELECT name FROM sqlite_master WHERE name IN (...)` | case-**sensitive** (`WHERE name='signals'` does not match `SIGNALS`) | adoption guard at `db.py:222` misses |
| `CREATE TABLE IF NOT EXISTS signals` | case-**insensitive** | no-op on the legacy table; migration records itself |
| `SELECT 1 FROM sqlite_master ... name = ?` | case-**sensitive** | `present is None` at `db.py:330` → `continue` at `db.py:332`, shape check skipped even with wrong types |
| `DROP TABLE signals` | case-**insensitive** | drops the legacy table, transaction commits, `_verify_reversal` (`db.py:358-360`) also case-sensitive and finds nothing |

All three guards are individually case-sensitive while the DDL they guard is not. Fixing only the apply-time guard leaves the revert-time hole; all three comparisons need normalising.

### Test coverage does not bind this

`tests/unit/test_migration_reversal.py` only ever creates lowercase `signals` (`:325-346`). Negative control: I made the lookup case-insensitive in a copy (`mut-d`) and the targeted suite still returned **18 passed, exit 0** — the suite cannot distinguish the broken from the fixed behaviour.

### Fix direction (verified, not written into the repo)

Compare identifiers case-insensitively (`lower(name)` / `COLLATE NOCASE`) in `_existing_objects`, in the `present` probe, and in `_verify_reversal`, and add a regression test with a case-variant pre-existing table at both apply and revert.

I confirmed the direction closes the hole: with `lower(name)` in the first two lookups, `signals`, `SIGNALS`, `Signals`, `sIgNaLs` are all refused at apply and the legacy row survives (`C:\GS5\s7b-tmp\probe_fix2.py`, exit 0):

```
signals  -> apply refused ... legacy rows: 1
SIGNALS  -> apply refused ... legacy rows: 1
Signals  -> apply refused ... legacy rows: 1
sIgNaLs  -> apply refused ... legacy rows: 1
```

Why this is a BLOCK and not a note: the gate rule is that any way to destroy data the migration did not create is a BLOCK. This is the F1 failure class, unchanged in impact (silent row loss + ledger deletion, no error, no backup), reduced only to a capitalisation difference in the table name. A legacy prototype table named `Signals` is an ordinary name in SQLite, where identifiers are case-insensitive by design.

---

## 3. Independent re-runs (item 3)

| Command (cwd = project directory) | Result |
|---|---|
| `python -m pytest -q --junitxml=C:\GS5\s7b-tmp\s7b-full.xml` | **270 tests, 0 failures, 0 errors, 0 skipped**, 194.558 s, exit 0 |
| `python -m pytest tests/unit/test_migration_reversal.py -q` | **18 passed**, exit 0 |
| `python -m compileall -q src scripts tests` | exit 0 |
| `git status --porcelain` after the runs | unchanged (only the two pre-existing untracked evidence files) |

Counts agree with the author's claims (270 suite, 18 targeted, compileall 0). The suite being green at HEAD is exactly why the case hole matters: the tests do not reach it.

---

## 4. Evidence file and sidecar (item 4)

`evidence/phase3-S6-20261112T182517Z.txt` + `.sha256`.

Sidecar matches the file itself: `3cff38ff185bf67882db229d0525657289b08dcf554782226b95b15cf727519f` ✓

Every recorded SHA-256 matches the file as committed at HEAD:

| file | recorded = measured | status |
|---|---|---|
| `migrations/rollback/0003_signals.down.sql` | `8b5e4263…aa42` | match |
| `src/guardian/storage/db.py` | `0e8a7739…051d` | match |
| `tests/unit/test_migration_reversal.py` | `772c255d…cef9` | match |
| `DECISIONS_LOG.md` | `f4266db8…6f9` | match |
| `PHASE3_PLAN.md` | `36c3d234…ab98` | match |
| `PROJECT_STATE.md` | `443c8a76…3484` | match |

External scripts it cites also match: `C:\GS5\mutation_probe.py` = `49d37663…0963`, `C:\GS5\s6_demo.py` = `5a460ad4…4038`.

Does the file describe the code that is there? For the code: **yes** — the content hashes pin the reviewed artefacts, and the described guard/shape/comment-strip behaviour is what `db.py` does, with the case exception above. Two defects in the packet itself:

1. **False flags in its own SUMMARY**: `s5_commit_unchanged=False` and `S5_PARENT_OK=False` (line 15), while `9a3b53a` is provably intact and its parent is `08ce5f3`. As printed, a reader concludes the S5 commit was altered. Either the flags are inverted/misnamed or the check is wrong — the packet needs correcting either way.
2. **Stale state block**: it records `HEAD: b2057d2` and lists `db.py` as `M` (uncommitted) because it was generated before `3deaf8c`. Honest but out of date; the hashes still match the committed content.

Minor: the embedded "DEMO SCRIPT SOURCE" is not byte-identical to `C:\GS5\s6_demo.py` (backslash escaping differs; 146 lines each). The script's own hash matches, so this is a rendering difference, not a content difference.

---

## 5. My mutations (item 5)

Throwaway copies under `C:\GS5\s7b-tmp\mut-a`, `mut-b`, `mut-d`; the repo was not touched.

| ID | mutation | result |
|---|---|---|
| MA | removed the adoption-guard block (`db.py:138-144`) | `test_apply_refuses_to_adopt_a_preexisting_table` **FAILED**, exit 1 |
| MB | reduced the shape comparison to names only | `test_revert_refuses_a_table_replaced_after_apply` **FAILED**, exit 1 |
| MD | made `_existing_objects` case-insensitive (negative control) | 18 passed, exit 0 — no test distinguishes |

MA and MB confirm the new guard and the new type comparison are genuinely bound by tests. MD confirms the case dimension is not.

---

## 6. New failure modes introduced (item 6)

**Confirmed: non-atomic DDL + ledger.** `conn.executescript(sql)` at `db.py:146` commits the schema, and only afterwards is the ledger row inserted at `db.py:147-151`. Simulating an interruption between them (execute the 0003 body, drop the ledger row):

```
2 DDL only; signal tables: ['signal_runs', 'signals'] | ledger: [1, 2]
3.1 apply_migrations refused: ... would adopt existing object(s)
    ['idx_signal_runs_window', 'idx_signals_run', 'signal_runs', 'signals'] ...
3.2 apply_migrations refused: (identical)
4 ledger still: [1, 2]
5 revert refused: MigrationError: migration 3 is not applied
```

The database is wedged: retries always fail, and the message describes the migration's **own** objects as adoption. All four CLI entry points call `apply_migrations` at startup (`scripts/collect.py:89`, `data_health.py:27`, `quarantine.py:43`, `signals.py:65`), so an interrupted first run makes the tool unusable until manual repair. Not destructive, but new — the previous `IF NOT EXISTS` would have re-applied and recorded. Fix direction: put the DDL and the ledger insert in one explicit transaction (SQLite supports transactional DDL), or detect "all declared objects present and shapes match" as a completed-but-unrecorded apply.

No other legitimate pre-existing-object path exists: nothing outside `migrations/` creates these tables (only `schema_migrations` at `db.py:109`), so fresh applies and normal upgrades are unaffected — verified by the clean control apply → `[1,2,3]` → revert → 3.

---

## 7. Docs vs code (item 7)

The invariant asserted in three places is false as implemented (same root cause as the must-fix, listed here as locations):

- `HANDOFF/01_STATE_SNAPSHOT.md:58-60` — "if any object a pending migration declares already exists, it raises `MigrationError` and records nothing. The ledger therefore only names migrations that created their own objects."
- `DECISIONS_LOG.md:133` (D-016 §8, last sentence) — "so the ledger only ever records migrations that created their own objects (S7 finding F1)."
- `PHASE3_PLAN.md:42` and `:50` — same claim.

Counter-example: `SIGNALS` in Case B is recorded as applied while creating nothing.

Other mismatches:

- `DECISIONS_LOG.md:136` (D-016 **Rollback**) still prescribes manual `DROP TABLE IF EXISTS signals; DROP TABLE IF EXISTS signal_runs;`, which D-016 §8 declares superseded. Already tracked as OPEN (R7) in the snapshot (`:103`), so disclosed rather than hidden.
- `migrations/0003_signals.sql:4-11` still says "Reverse (S6) is deliberately NOT implemented in this stage", contradicting the shipped `rollback/0003_signals.down.sql` and D-016 §8. The file is frozen and hash-pinned, so the stale comment cannot simply be edited; it needs a pointer elsewhere.

Consistent: `PROJECT_STATE.md` and `PHASE3_PLAN.md:50` (270/270, S6 PASS, S7 re-review pending), `01_STATE_SNAPSHOT.md:43` (396 lines, 18 tests) — all match my measurements. `HANDOFF/MANIFEST.sha256`: 8 entries, 0 mismatches.

---

## 8. Findings summary

**Must fix — 1**

1. **Case-sensitive identifier checks let a pre-existing table be adopted and then dropped, silently** (`db.py:138-144`, `db.py:222`, `db.py:327-332`, `db.py:358-360`). A table named `SIGNALS`/`Signals`/`sIgNaLs` with the same nine column names — even with different types — is adopted, recorded as 0003, then dropped by `revert_migration(3)` with the rows lost and the ledger row deleted, no error at any step. Impact and class are identical to F1; only the trigger is smaller. Fix: case-insensitive comparison in all three lookups plus a regression test; verified working direction in §2.

**Worth considering — 2**

1. **DDL and ledger insert are not atomic** (`db.py:146-151`): an interrupted apply leaves a database that can never be retried and whose error message blames adoption of its own objects; every CLI entry point fails. Wrap in one transaction, or recognise a completed-but-unrecorded apply.
2. **The evidence packet's own flags contradict the repository** (`phase3-S6-20261112T182517Z.txt:15`, SUMMARY line): `S5_IS_HEAD/S5_PARENT_OK/s5_commit_unchanged` read as "S5 was altered", while `9a3b53a` is intact. Correct or rename them, and refresh the HEAD/`M db.py` state block.

**Notes — 3**

1. `0003_signals.sql:4-11` still declares the reverse unimplemented (frozen file; pointer needed).
2. `_declared_shape` (`db.py:229-232`) searches raw SQL including comments while `_created_objects` strips them — asymmetric; reachable only as a false refusal or with an edited hash-pinned forward file.
3. `_CREATE_RE` does not match quoted identifiers (`CREATE TABLE "signals"`), so a future migration written that way would escape the adoption guard and be unreversible; not applicable to 0003.

---

## 9. Scope and what I could not verify

Verified by execution at HEAD: branch/HEAD/log/status, chain linearity, `9a3b53a` integrity, the F1 attack and its variants (10 databases), the crash window, clean apply/revert, 270-test suite, 18-test targeted file, `compileall`, six file hashes plus the sidecar and two external scripts, the HANDOFF manifest, four doc files, and three mutations of my own.

Not verified:

- **origin/remote state** — no fetch/push permitted, so "origin is at b2057d2" is unconfirmed.
- **Live database impact** — no `.sqlite3` exists in the tree (`data/` absent), so I could not measure what the new guard does to a deployed database; the four CLI entry points were read, not run.
- **The author's six mutation probes and demo** — I did not execute `C:\GS5\mutation_probe.py` or `C:\GS5\s6_demo.py`; I verified their hashes and independently reproduced two of the six mutations (plus one control).
- No test was added or modified; no file inside `C:\GS5\repo` was written by this review.
