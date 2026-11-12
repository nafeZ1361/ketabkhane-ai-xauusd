# 01 — STATE SNAPSHOT

Snapshot written **2026-11-12**, after two independent S7 reviews returned `BLOCK` and both findings
were fixed. If `git rev-parse HEAD` differs from the table, this file is history — re-derive first.

## Git

| Item | Value |
|---|---|
| Branch | `fix/w1-timezone-validation` |
| HEAD when these hashes were taken | `3deaf8c` plus the round-2 fix commit (see `git log --oneline -3`) |
| Commits | `9a3b53a` S5 → `2e56ae7` S6 → `f3f6644`, `b2057d2` handoff docs → `3deaf8c` F1 fix → round-2 fix |
| `main` | `1dad9588083f210fca868f49358aff44826e6f2f` (unchanged) |
| Parallel branch `fix/xauusd-guardian-w1-timezone` | `76d468eda3e15e2c7d87a4fdcfe0f7b45c620b45` (unchanged, deliberately kept) |
| S5 commit | `9a3b53a` — accepted baseline, never amended |

The S6 evidence records `S5_IS_HEAD: False`; correct — HEAD has moved past S5. The baseline check is
"is `9a3b53a` still an ancestor", not "is it HEAD".

## S7 review history

| Round | Verdict | Finding | Fix |
|---|---|---|---|
| 1 | **BLOCK** | **F1**: a pre-existing table named `signals` with the same column names was adopted by `CREATE TABLE IF NOT EXISTS`; apply recorded 0003 anyway; the reverse dropped it and deleted the ledger row — legacy rows destroyed, no error. R1 had understated the risk as "regenerable 0003-era data". | `apply_migrations` refuses to record a migration whose declared objects already exist; shape check widened to `(column, declared type)`; comments stripped before the whitelist scan |
| 2 | **BLOCK** | **F1b**: identifiers were compared case-sensitively while SQLite is case-insensitive — a table created as `SIGNALS` slipped past the guard and was adopted, then dropped by the reverse. The reviewer also flagged that DDL and the ledger row were not atomic, so an interrupted apply left objects unrecorded and the retry reported a misleading "adoption". | case-insensitive comparison in `_existing_objects`, `_check_declared_shapes`, `_verify_reversal`, `_checked_down_statements`; `apply_migrations` runs DDL + ledger insert in one `BEGIN IMMEDIATE ... COMMIT` |
| 3 | pending | — | re-review requested |

## The delta — committed state (post round-2 fix)

Paths relative to `ایجنت/xauusd-guardian/`. SHA-256 over raw file bytes as checked out.

| Path | State | SHA-256 |
|---|---|---|
| `src/guardian/storage/db.py` | M (486 lines) | `9241c6bd77afb364c059317df80857240254f716ceff623d02bec1733d23c248` |
| `tests/unit/test_migration_reversal.py` | new (441 lines, 22 tests) | `7535759f0f9b0213affd231ac409f0fa90353481154a9cbc9b312ee0c5953de4` |
| `migrations/rollback/0003_signals.down.sql` | new (unchanged since S6) | `8b5e42635e887387ec4dc44d2d7dcf10d59476ce12a243b41e1c08cc7437aa42` |
| `DECISIONS_LOG.md` | M (D-016 §8) | `36a82fa89f2d3925f025ddcbcb4ed44593d8f2d9cf5a5b45c18ea7de10cd27d1` |
| `PHASE3_PLAN.md` | M (§5 + status/gate lines) | `93f469500e61861a481f336b6e1418cc7f9a2238b3dcc75576ec3a47f52625b3` |
| `PROJECT_STATE.md` | M (Phase 3 row) | `625af067112452c74093d2a051691a1cf057f80fa27da9ef14f2b6ab1afb3054` |
| `evidence/phase3-S6-20261112T191535Z.txt` | new (authoritative) | `96a05de862b5db20eed3b5a6bbb005ce1e3c339b04e17560cbf8241f131a5a1d` |
| `evidence/phase3-S6-20261112T191535Z.txt.sha256` | new | `00ff33b74f931fe550defdfbb58114fc8865879c00f705e353961a77b546f16f` |
| `evidence/phase3-S6-20261112T182517Z.txt` | committed historical (pre-F1b) | `3cff38ff…519f` |
| `evidence/phase3-S6-20261109T173019Z.txt` | committed historical (pre-F1) | `7a6a7f51…a85a` |
| `evidence/phase3-S6-20261109T170723Z.txt` | **local-only**, abandoned | — |
| `evidence/phase3-S5-20261108T202628Z.txt` | **local-only**, S5 evidence, not authorized for commit | — |

## What the migrations code guarantees (behaviour, not marketing)

1. **Additive.** `0003_signals.sql` is `CREATE ... IF NOT EXISTS` only; nothing in `0001`/`0002` is
   altered. Its digest is pinned in `schema_migrations`.
2. **No adoption.** `apply_migrations` refuses to record a migration when any object it declares
   already exists — compared **case-insensitively**, as SQLite does. The ledger therefore only names
   migrations that created their own objects.
3. **Atomic apply.** A migration's DDL and its ledger row commit in one `BEGIN IMMEDIATE ... COMMIT`;
   a failure leaves neither. The realistic crash window that could create an unrecorded table is gone.
4. **Reversible, narrowly.** `reversal_plan` validates before acting: version applied, no later
   version applied, forward digest unchanged, exactly one strict `NNNN_name.down.sql`, every statement
   a `DROP` of an object that forward created (comments ignored, case-insensitive), each table's live
   `(column, type)` still matching the declaration. `revert_migration` then executes it in one
   transaction, requires that none of those objects remain, deletes the ledger row, and rolls back on
   any failure.
5. **Policy.** Reverses are DROP-only; a reverse needing `ALTER` requires a new decision.

## Test and tool results

| Command | Result |
|---|---|
| `pytest tests/unit/test_migration_reversal.py -v` | 22 passed, exit 0 |
| `pytest -q` | 274 passed, 0 failed, 0 error, 0 skipped, exit 0 |
| `python -m compileall -q src scripts tests` | exit 0 |
| mutation probes | `probes=8 unkilled=0` |
| live demo | 8 steps incl. lowercase adoption, `SIGNALS` adoption, transaction demo, exit 0 |

Suite history: 252 (S5) → 267 (S6) → 270 (F1) → **274** (F1b). No test deleted, skipped or weakened.

## Evidence

| File | Role |
|---|---|
| `evidence/phase3-S6-20261112T191535Z.txt` | **authoritative**: refs, hashes, 274 tests, 8 mutations, 8-step demo + demo source |
| `…191535Z.txt.sha256` | sidecar digest |
| `…20261112T182517Z.txt` | historical: pre-F1b fix (F1 fixed, case bug present) |
| `…20261109T173019Z.txt` | historical: pre-F1 |
| `…20261109T170723Z.txt` | abandoned attempt; local-only |

## Residuals

| # | Residual | Status |
|---|---|---|
| R1 | adoption of a same-named table, then dropped by the reverse | **FIXED** — refused at apply time, case-insensitive; regression tests ×4 + mutation M5/M7 |
| R1b | case-sensitive identifier comparison | **FIXED** — all four lookups normalise case; parametrised test over `SIGNALS`/`Signals`/`sIgNaLs`; mutation M7 |
| R1c | non-atomic apply (DDL committed before ledger row) | **FIXED** — one transaction; test `test_failed_migration_leaves_no_partial_schema`; mutation M8 |
| R2 | `_check_declared_shapes` docstring overclaimed | **FIXED** — docstring now states it catches drift, and why adoption cannot reach it |
| R3 | header of `0003_signals.sql` still says the reverse is "deliberately NOT implemented" | **OPEN, accepted** — hash-pinned; editing breaks every applied database. Corrected in the down file header and D-016 §8 |
| R4 | superseded evidence files carry no banner of their own | **OPEN, accepted** — evidence is never edited; each new file's `NOTE` names its predecessors |
| R5 | status lines lagged reality | **FIXED** — `PHASE3_PLAN.md` and `PROJECT_STATE.md` now state S6 PASS / S7 BLOCK ×2 + fixes |
| R6 | mutation-probe source not embedded in evidence | **OPEN, accepted** — path + digest recorded; the probe lives outside the repo |
| R7 | D-016's trailing `**Rollback:**` line still shows the old manual `DROP TABLE IF EXISTS` | **OPEN** — superseded by §8; fix when the S7 verdict is recorded |

## Open decisions that are NOT yours to close

| ID | Question | Owner |
|---|---|---|
| F1 (branch) | Two parallel branches implement the same W1 timezone fix. Human decided: keep both, delete nothing. | Human |
| D-003 | Symbol policy amendment `spot_metal_usd_v2` | Human (pending) |
| S5-R1 | Stale signal survives when a bar revision makes a published signal disappear | Next stage, by decision |
| S5-R2 | `scripts/replay_signals.py` behaviour change has no automated test | Next stage, by decision |
