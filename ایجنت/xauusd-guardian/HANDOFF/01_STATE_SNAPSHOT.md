# 01 — STATE SNAPSHOT

Snapshot written **2026-11-12**, after the S7 review returned `BLOCK` and finding F1 was fixed.
If `git rev-parse HEAD` differs from the table, this file is history — re-derive before acting.

## Git

| Item | Value |
|---|---|
| Branch | `fix/w1-timezone-validation` |
| HEAD when these hashes were taken | `b2057d2fe74c3dd4f89a6d3943b51065e6194e52` (handoff docs) |
| Commit carrying this snapshot | the S7/F1 fix commit on top of `b2057d2`; find it with `git log --oneline -3` |
| `main` | `1dad9588083f210fca868f49358aff44826e6f2f` (unchanged) |
| Parallel branch `fix/xauusd-guardian-w1-timezone` | `76d468eda3e15e2c7d87a4fdcfe0f7b45c620b45` (unchanged, deliberately kept) |
| `origin/fix/w1-timezone-validation` | `b2057d2` at push time; the F1 fix commit is one ahead until pushed |
| S5 commit | `9a3b53a` — accepted baseline, never amended |
| S6 commit | `2e56ae7` — `feat(s6): reversible migration 0003 with guarded reversal` |
| Handoff commits | `f3f6644`, `b2057d2` |

The S6 evidence records `S5_IS_HEAD: False`; that is correct — HEAD has moved past the S5 commit
since `2e56ae7`. The baseline check is "is `9a3b53a` still an ancestor of HEAD", not "is it HEAD".

## S7 review outcome

| Item | Value |
|---|---|
| Reviewer | independent Inspector, read-only, did not write the code |
| Verdict | **BLOCK** — one must-fix (F1) |
| F1 | A pre-existing table named `signals` with the same column names was **adopted** by `CREATE TABLE IF NOT EXISTS`; apply recorded 0003 anyway; `revert_migration` then dropped it and deleted the ledger row, destroying legacy rows with no error. |
| Why it mattered | The S6 shape check compared column *names* only, while its docstring claimed this exact case was guarded. R1 had classified the risk as "regenerable 0003-era data", which was wrong: the adopted table can be arbitrary legacy data. |
| Fix | `apply_migrations` now queries `sqlite_master` for every object a pending migration declares and raises `MigrationError` if any already exists — a migration is only recorded when it created its own objects. The shape check was widened from names to `(name, declared type)` for post-apply drift. `_created_objects` now strips comments so a `--` comment cannot widen the reverse whitelist. |
| Tests | 3 new regression tests: adoption refused at apply; type-only drift refused at revert; a comment mentioning `CREATE TABLE bars` cannot legalise a `DROP`. |
| Result | 18 targeted, **270** suite, `compileall` exit 0, **6/6 mutation probes killed** |
| Status | **fix implemented, committed, awaiting S7 re-review** |

## The S6 + F1 delta — as committed

Paths relative to `ایجنت/xauusd-guardian/`. SHA-256 over raw file bytes as checked out.

| Path | State | SHA-256 |
|---|---|---|
| `src/guardian/storage/db.py` | M (469 lines) | `0e8a77396752c6c11e7436ce135d3447f51199a1b85c2a710804e74913b3051d` |
| `tests/unit/test_migration_reversal.py` | new (396 lines, 18 tests) | `772c255db3cb5444c1f1510accb3e491c3a4beae2c4db64dcc9127ea2cc5cef9` |
| `migrations/rollback/0003_signals.down.sql` | new (unchanged by F1) | `8b5e42635e887387ec4dc44d2d7dcf10d59476ce12a243b41e1c08cc7437aa42` |
| `DECISIONS_LOG.md` | M (D-016 §8) | `f4266db8ac76a570a3ae363768c847b72e8b370b6029f22c8fbe5bcae7cf66f9` |
| `PHASE3_PLAN.md` | M (§5 + status/gate lines) | `36c3d23446ffe0c7d28df3d2b735716b1ce6a82e204a9b368fd8815acef5ab98` |
| `PROJECT_STATE.md` | M (Phase 3 row) | `443c8a76f9e2b6c893ba3ebd1ea9fa364c2f2ad4b430e482122fbf0583e43484` |
| `evidence/phase3-S6-20261112T182517Z.txt` | new (authoritative) | `3cff38ff185bf67882db229d0525657289b08dcf554782226b95b15cf727519f` |
| `evidence/phase3-S6-20261112T182517Z.txt.sha256` | new | `2c24faab9d2d0fdda62d309d50c073e9d832f874dba3ad1537f29c5ffc7a789e` |
| `evidence/phase3-S6-20261109T173019Z.txt` (+ sidecar) | committed historical snapshot (pre-F1) | `7a6a7f51…a85a` / `44c7dbd6…fb55` |
| `evidence/phase3-S6-20261109T170723Z.txt` | **local-only**, abandoned attempt | — |
| `evidence/phase3-S5-20261108T202628Z.txt` | **local-only**, S5 evidence, not authorized for commit | — |

## What the migrations code does (behaviour, not marketing)

- `0003_signals.sql` is additive: `CREATE ... IF NOT EXISTS` only, no `ALTER`/`DROP` of `0001`/`0002`.
  Never edited; its digest is pinned in `schema_migrations`.
- `apply_migrations` refuses **adoption**: if any object a pending migration declares already exists,
  it raises `MigrationError` and records nothing. The ledger therefore only names migrations that
  created their own objects.
- `migrations/rollback/0003_signals.down.sql`: `DROP TABLE signals;` then `DROP TABLE signal_runs;`,
  plain `DROP` so a missing table fails loudly inside the transaction.
- `reversal_plan(conn, migrations_dir, version)` validates before acting: version applied, no later
  version applied, forward digest still matches, exactly one strict `NNNN_name.down.sql`, every
  statement is a `DROP` of an object the forward created (comments ignored), each table's live
  `(column, type)` still matches the declaration. Returns the plan including `down_sha256`.
- `revert_migration(...)` runs the plan inside one `BEGIN IMMEDIATE ... COMMIT`, enforces the
  post-condition (none of those objects may remain), then deletes the ledger row; any failure rolls
  the whole reverse back.
- Policy: reverses are DROP-only. A migration whose reverse needs `ALTER` requires a new decision.

## Test and tool results

| Command | Result |
|---|---|
| `pytest tests/unit/test_migration_reversal.py -v` | 18 passed, exit 0 |
| `pytest -q` | 270 passed, 0 failed, 0 error, 0 skipped, exit 0 |
| `python -m compileall -q src scripts tests` | exit 0 |
| mutation probes | `probes=6 unkilled=0` |
| live demo | 7 steps incl. adoption refusal, exit 0 |

Suite history: 252 (S5) → 267 (S6) → **270** (F1 fix). No test deleted, skipped or weakened.

## Evidence

| File | Role |
|---|---|
| `evidence/phase3-S6-20261112T182517Z.txt` | **authoritative**: refs, hashes, 270 tests, 6 mutations, 7-step demo + demo source |
| `…20261112T182517Z.txt.sha256` | sidecar digest of the above |
| `evidence/phase3-S6-20261109T173019Z.txt` | historical: the pre-F1 state the S6 Inspector passed |
| `evidence/phase3-S6-20261109T170723Z.txt` | abandoned attempt; superseded, hashes no longer match |

## Residuals

| # | Residual | Status |
|---|---|---|
| R1 | adoption of a same-named table, then dropped by the reverse | **FIXED** (S7 F1) — refused at apply time, regression test + mutation probe |
| R2 | `_check_declared_shapes` docstring overclaimed | **FIXED** — docstring now states it catches drift, and that adoption cannot reach it |
| R3 | header of `0003_signals.sql` still says the reverse is "deliberately NOT implemented" | **OPEN, accepted** — the file is hash-pinned; editing it breaks every applied database. The down file header and D-016 §8 carry the correction. |
| R4 | superseded evidence files carry no banner of their own | **OPEN, accepted** — never edit evidence; the current file's `NOTE` line names both superseded files |
| R5 | status lines lagged reality | **FIXED** — `PHASE3_PLAN.md` line 3, its gate line and `PROJECT_STATE.md` now state S6 PASS / S7 BLOCK+F1 fixed |
| R6 | mutation-probe source not embedded in evidence | **OPEN, accepted** — path + digest recorded; the probe lives outside the repo |
| R7 | D-016's trailing `**Rollback:**` line still shows the old manual `DROP TABLE IF EXISTS` | **OPEN** — points at a statement superseded by §8; fix in the commit that records the S7 verdict |

## Open decisions that are NOT yours to close

| ID | Question | Owner |
|---|---|---|
| F1 (branch) | Two parallel branches implement the same W1 timezone fix. Human decided: keep both, delete nothing. | Human |
| D-003 | Symbol policy amendment `spot_metal_usd_v2` | Human (pending) |
| S5-R1 | Stale signal survives when a bar revision makes a published signal disappear | Next stage, by decision |
| S5-R2 | `scripts/replay_signals.py` behaviour change has no automated test | Next stage, by decision |
