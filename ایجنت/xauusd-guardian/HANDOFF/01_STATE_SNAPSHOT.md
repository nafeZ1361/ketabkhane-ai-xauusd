# 01 — STATE SNAPSHOT

Snapshot written **2026-11-12**, after **three** independent S7 reviews returned `BLOCK` and every
finding was fixed. If `git rev-parse HEAD` does not contain this file's commit, re-derive first.

## Git

| Item | Value |
|---|---|
| Branch | `fix/w1-timezone-validation` |
| Commit chain | `9a3b53a` S5 → `2e56ae7` S6 → `f3f6644`, `b2057d2` handoff → `3deaf8c` F1 → `69e783d` F1b → the F1c commit that carries this file |
| `main` | `1dad9588083f210fca868f49358aff44826e6f2f` (unchanged) |
| Parallel branch `fix/xauusd-guardian-w1-timezone` | `76d468eda3e15e2c7d87a4fdcfe0f7b45c620b45` (unchanged, deliberately kept) |
| S5 commit | `9a3b53a` — accepted baseline, never amended |

`S5_IS_HEAD: False` in the evidence is correct: HEAD has moved past S5. The baseline check is
"is `9a3b53a` an ancestor", not "is it HEAD".

## S7 review history (three rounds, all findings fixed)

| Round | Verdict | Finding | Fix |
|---|---|---|---|
| 1 | BLOCK | **F1** — a pre-existing same-named table was adopted by `CREATE TABLE IF NOT EXISTS`, recorded as applied, then dropped by the reverse | adoption refused at apply time; shape check widened; comments stripped before the whitelist scan |
| 2 | BLOCK | **F1b** — identifiers were compared case-sensitively while SQLite is not, so `SIGNALS` slipped through; apply was not atomic | case-insensitive comparison everywhere; DDL + ledger in one transaction |
| 3 | BLOCK | **F1c** — (i) databases written by the pre-fix build have no provenance and still lose adopted rows; (ii) an unqualified `DROP` can hit `TEMP` or an `ATTACH`ed schema; (iii) quoted / `main.`-qualified `CREATE` was not parsed, so adoption was recorded | **measured provenance** (`schema_objects`), reverse requires it, every DROP qualified with `main.`, post-condition checks every schema, SQLite's four identifier spellings parsed |
| 4 | pending | — | re-review requested |

## What the migrations code guarantees now

1. **Additive.** `0003_signals.sql` is `CREATE ... IF NOT EXISTS` only; `0001`/`0002` untouched; digest
   pinned in `schema_migrations`.
2. **No adoption.** `apply_migrations` refuses a migration whose declared objects already exist —
   bare, double-quoted, bracketed, backticked or schema-qualified, any case.
3. **Atomic apply.** DDL, ledger row and provenance commit in one `BEGIN IMMEDIATE ... COMMIT`.
4. **Measured provenance.** Each apply diffs `main.sqlite_master` before/after and stores the objects
   it actually created in `schema_objects`. The ledger records what happened, not what the text said.
5. **Narrow reverse.** `reversal_plan` requires provenance (a database applied before provenance
   existed is refused, not guessed at), no later version, an unchanged forward digest, exactly one
   strict `NNNN_name.down.sql`, and only `DROP TABLE`/`DROP INDEX` of objects recorded as created —
   targeting `main`.
6. **Verified reverse.** Drops are executed with `main.` qualification inside one transaction; the
   post-condition then requires that no recorded object survives in **any** schema and that no object
   the migration did not create disappeared from any schema. Otherwise everything rolls back.
7. **Policy.** Reverses are DROP-only; a reverse needing `ALTER` requires a new decision.

## The delta — committed state (post F1c)

Paths relative to `ایجنت/xauusd-guardian/`. SHA-256 over raw file bytes as checked out.

| Path | State | SHA-256 |
|---|---|---|
| `src/guardian/storage/db.py` | M (598 lines) | `7a5e06168818bda6b35c14556bc4f447e43169f5182b87543464b849e8d938bb` |
| `tests/unit/test_migration_reversal.py` | new (561 lines, 27 tests) | `80aca7c330216b400bf9d3d0262a469a46966ea618deefd48e80b2a2d5d8391f` |
| `migrations/rollback/0003_signals.down.sql` | new (unchanged since S6) | `8b5e42635e887387ec4dc44d2d7dcf10d59476ce12a243b41e1c08cc7437aa42` |
| `DECISIONS_LOG.md` | M (D-016 §8 rewritten) | `398a0c33c2b18d139d4fcb7190fac5f84caaf3d020d3b4d47c1884ac81fa17b5` |
| `PHASE3_PLAN.md` | M (§5 + status/gate lines) | `ef90bfbc481df58d638643c4f94547cf9eb63d2822a7a6b47c1eee474536f8b3` |
| `PROJECT_STATE.md` | M (Phase 3 row) | `71f697f6b2ea5c1fc459b9b2a4d7737e7e23468dafaa3215a2ffdf6efe494584` |
| `evidence/phase3-S6-20261112T203848Z.txt` | new (authoritative) | `6266b7c7507d5af80aa6aa381e7a6690f0f471424135a0b0681821303794e771` |
| `evidence/phase3-S6-20261112T203848Z.txt.sha256` | new | `599096dd1ad616ef1642042dca6a5bf2e5ba3cf179da523d7f45832bed6860eb` |
| older `evidence/phase3-S6-*` files | committed history (pre-F1, pre-F1b, pre-F1c) | see each file |
| `evidence/phase3-S6-20261109T170723Z.txt`, `evidence/phase3-S5-…txt` | **local-only**, not committed | — |

## Test and tool results

| Command | Result |
|---|---|
| `pytest tests/unit/test_migration_reversal.py -v` | 27 passed, exit 0 |
| `pytest -q` | 279 passed, 0 failed, 0 error, 0 skipped, exit 0 |
| `python -m compileall -q src scripts tests` | exit 0 |
| mutation probes | 11 probes, all killed (`unkilled=0`) |
| live demo | 9 steps: apply, revert, re-apply, hostile down, lowercase adoption, `SIGNALS` adoption, legacy DB refusal |

Suite history: 252 (S5) → 267 (S6) → 270 (F1) → 274 (F1b) → **279** (F1c).

## Evidence

| File | Role |
|---|---|
| `evidence/phase3-S6-20261112T203848Z.txt` | **authoritative**: refs, hashes, 279 tests, 11 mutations, 9-step demo + demo source |
| `…203848Z.txt.sha256` | sidecar digest |
| `…191535Z`, `…182517Z`, `…173019Z` | historical: pre-F1c, pre-F1b, pre-F1 |

## Residuals

| # | Residual | Status |
|---|---|---|
| R1 | adoption of a same-named table | **FIXED** (F1) — refused at apply |
| R1b | case-sensitive identifier comparison | **FIXED** (F1b) — inventory normalises case |
| R1c | non-atomic apply | **FIXED** (F1b) — one transaction |
| R1d | databases applied **before** provenance tracking (commits `2e56ae7`, `3deaf8c`) can still lose an adopted table on revert | **FIXED by refusal** (F1c) — no provenance ⇒ `revert_migration` refuses with an explicit instruction to audit or rebuild. Those databases are not migrated automatically and must be treated as suspect. |
| R2 | shape-check docstring overclaimed | **FIXED** — states exactly what it checks |
| R3 | header of `0003_signals.sql` says the reverse is "deliberately NOT implemented" | **OPEN, accepted** — hash-pinned; corrected in the down file header and D-016 §8 |
| R4 | historical evidence files carry no banner of their own | **OPEN, accepted** — evidence is never edited; each current file's `NOTE` names its predecessors |
| R5 | status lines lagged reality | **FIXED** — plan and state now say S6 PASS / S7 BLOCK ×3 + fixes |
| R6 | mutation-probe source not embedded in evidence | **OPEN, accepted** — path + digest recorded; the probe lives outside the repo |
| R7 | D-016's trailing `**Rollback:**` line still shows the old manual statement | **OPEN** — superseded by §8; fix when the S7 verdict is recorded |

## Open decisions that are NOT yours to close

| ID | Question | Owner |
|---|---|---|
| F1 (branch) | Two parallel branches implement the same W1 timezone fix. Human decided: keep both, delete nothing. | Human |
| D-003 | Symbol policy amendment `spot_metal_usd_v2` | Human (pending) |
| S5-R1 | Stale signal survives when a bar revision makes a published signal disappear | Next stage, by decision |
| S5-R2 | `scripts/replay_signals.py` behaviour change has no automated test | Next stage, by decision |
