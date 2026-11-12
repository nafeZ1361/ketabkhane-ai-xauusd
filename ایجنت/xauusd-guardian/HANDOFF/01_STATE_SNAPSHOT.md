# 01 — STATE SNAPSHOT

Snapshot taken **2026-11-12** from the working clone `C:\GS5\repo`.
If `git rev-parse HEAD` differs from the table below, this file is history — re-derive before acting.

## Git

| Item | Value |
|---|---|
| Branch | `fix/w1-timezone-validation` |
| HEAD now | `f3f6644768a64f25757bcbb606c233461644989c` — handoff commit (see the chain below) |
| HEAD at S6 inspection | `9a3b53af95267c6ecaeca6b567006f671786ecd7` — `feat(signals): complete Phase 3 S5 signal service` |
| HEAD parent | `08ce5f331a72d5b13c5757654e098ac397ba9d1b` |
| `main` | `1dad9588083f210fca868f49358aff44826e6f2f` (unchanged) |
| Parallel branch `fix/xauusd-guardian-w1-timezone` | `76d468eda3e15e2c7d87a4fdcfe0f7b45c620b45` (unchanged, deliberately kept) |
| `origin/fix/w1-timezone-validation` | `f3f6644` — in sync since 2026-11-12 (before that `08ce5f3`; the S5 commit was local-only) |
| S6 commit | `2e56ae7` — `feat(s6): reversible migration 0003 with guarded reversal` |
| Handoff commit | `f3f6644` — `docs(handoff): agent handoff pack for S7 and beyond` |

## S6 delta — the working-tree change set as inspected

10 paths, all inside S6 scope. Hashes are SHA-256 over **raw file bytes** (CRLF as checked out).

| Path (relative to `ایجنت/xauusd-guardian/`) | State | SHA-256 |
|---|---|---|
| `src/guardian/storage/db.py` | M (+324 lines) | `79e995146e4d6e7c5080ffb106f75396e7388587cfe6be92dde0de450dfb32e0` |
| `tests/unit/test_migration_reversal.py` | new (317 lines, 15 tests) | `20d1617dc98253c485fe31bf1bf336347271aa7a95adc25498ffb0d2cc888d24` |
| `migrations/rollback/0003_signals.down.sql` | new | `8b5e42635e887387ec4dc44d2d7dcf10d59476ce12a243b41e1c08cc7437aa42` |
| `DECISIONS_LOG.md` | M (D-016 §8) | `f9baa233e223f2f767f3927d106dc6cb763ec9d5fbdee26c25fcc142929d8482` |
| `PHASE3_PLAN.md` | M (§5 + gate line) | `4dfc2a50955b3082cc284d840c60c547f07ed4a22da4d64340df2bf5fe70b3a4` |
| `PROJECT_STATE.md` | M (Phase 3 row) | `481943cfd05dfc11be48bb464f713efd75b1fc1d58317fcde5c9c51ce5c34493` |
| `evidence/phase3-S6-20261109T173019Z.txt` | new | `7a6a7f51ea870e6ef6a9d2c7570b84824302ef9805a1f6da9118b7e4f4fea85a` |
| `evidence/phase3-S6-20261109T173019Z.txt.sha256` | new | `44c7dbd64439b790529bbb2b286b82576676918dc22f2b474867992f8b3dfb55` |
| `evidence/phase3-S6-20261109T170723Z.txt` | local-only — **superseded attempt, wrong hashes, not committed, do not audit against it** | — |
| `evidence/phase3-S5-20261108T202628Z.txt` | untracked S5 evidence — **local-only; must not be added without authorization** | — |

Of these ten paths, the first eight are committed with the handoff change set (see the git table above);
the two evidence files marked local-only stay untracked on purpose. A fresh clone will therefore not
contain them, and nothing in this repository depends on them.

The handoff pack itself (`HANDOFF/`, and a one-paragraph `README.md` status update) is an
**additional, additive** change set; it does not touch any file above.

## What S6 actually does (behaviour contract, not marketing)

- Forward `0003_signals.sql` is additive: three `CREATE ... IF NOT EXISTS` (two tables + two
  indexes), no `ALTER`/`DROP` of `0001`/`0002`. Never edited, hash pinned in `schema_migrations`.
- `migrations/rollback/0003_signals.down.sql`: `DROP TABLE signals;` then `DROP TABLE signal_runs;`.
  Plain `DROP` (no `IF EXISTS`) so a missing table fails loudly inside the transaction.
- `guardian.storage.db.reversal_plan(conn, migrations_dir, version)` resolves and validates the
  reverse **without acting**: version applied, no later version applied, forward hash still matches
  the ledger, exactly one strict `NNNN_name.down.sql`, every statement is a `DROP` of an object the
  paired forward created, each table's live columns still match the declared ones.
  Returns `ReversalPlan(version, forward_filename, forward_sha256, down_filename, down_sha256,
  statements, tables, indexes)` — the down file digest is how you cite a reversal.
- `revert_migration(...)` runs the plan inside one `BEGIN IMMEDIATE ... COMMIT`, then enforces the
  post-condition (none of those objects may remain in `sqlite_master`), then deletes the
  `schema_migrations` row. Any failure rolls the whole thing back.
- Policy: reverses are **DROP-only**. A future migration whose reverse needs `ALTER` requires a new
  decision, not a wider whitelist.

## Test and tool results (2026-11-09, re-verified 2026-11-12)

| Command | Result |
|---|---|
| `pytest tests/unit/test_migration_reversal.py -v` | 15 passed, exit 0 |
| `pytest -q` | 267 passed, 0 failed, 0 error, 0 skipped, exit 0 |
| `python -m compileall -q src scripts tests` | exit 0 |
| mutation probes (4) | all four protective tests went red: `probes=4 unkilled=0` |
| live demo | apply → seed → revert → re-apply → guard refusal, exit 0 |

Suite grew 252 (S5) → **267** (S6: +15). No test was deleted, skipped or weakened.

## Evidence

| File | Role |
|---|---|
| `evidence/phase3-S6-20261109T173019Z.txt` | authoritative S6 evidence: refs, hashes, tests, mutation, demo output, demo source |
| `…173019Z.txt.sha256` | sidecar digest of the evidence file |
| `evidence/phase3-S6-20261109T170723Z.txt` | earlier attempt; superseded, its hashes no longer match the tree |

Everything in the authoritative file was produced by real commands; nothing was hand-written.
Reproduce with `HANDOFF/artifacts/` plus the commands in `03_AGENT_PROTOCOL.md` §5.

## Accepted residuals (known, non-blocking, deliberately not fixed after the verdict)

Fixing these changes the exact tree the Inspector passed, so they are queued for the commit that
a human authorizes — not for a silent post-verdict edit.

| # | Residual | Risk | Suggested fix |
|---|---|---|---|
| R1 | A table named `signals` that existed **before** 0003 with the **identical** column list would be "adopted" by `CREATE TABLE IF NOT EXISTS` and later dropped by the reverse. The shape check compares column names only. | Data at risk is 0003-era signal data (regenerable); no such DB exists on the official lineage | Record object provenance at apply time (changes S5 behaviour → needs a decision), or accept and document |
| R2 | Docstring of `_check_declared_shapes` claims it "guards the adoption case"; it guards *drift*, not identical-shape adoption | Comment only; behaviour matches D-016 §8 | Reword the docstring |
| R3 | Header of `0003_signals.sql` still says the reverse is "deliberately NOT implemented" | Misleading to readers; file is hash-pinned, editing it breaks every applied DB | Leave byte-identical; the down file header + D-016 §8 carry the correction |
| R4 | `evidence/phase3-S6-20261109T170723Z.txt` carries no banner of its own saying it is superseded | An auditor may pick the wrong file | Add a `SUPERSEDED BY …` line, or move it under `evidence/superseded/` |
| R5 | `PHASE3_PLAN.md` line 3 still reads "S5 implemented (252/252) … S6–S7 OPEN" while line 50 and reality say otherwise | Status drift | Update when the S6 verdict is recorded |
| R6 | The mutation-probe source is not embedded in the evidence file (only its path and hash) | Probe results are checkable, not re-runnable from the repo alone | Embed the source, or place helper scripts under `evidence/` |
| R7 | D-016's trailing `**Rollback:**` line still gives the old manual `DROP TABLE IF EXISTS …` statement | Contradicts D-016 §8 | Point it at `revert_migration` |

## Open decisions that are NOT yours to close

| ID | Question | Owner |
|---|---|---|
| F1 | Two parallel branches implement the same W1 timezone fix (`fix/w1-timezone-validation` vs `fix/xauusd-guardian-w1-timezone`). Human decided: **keep both, delete nothing**. | Human |
| D-003 | Symbol policy amendment `spot_metal_usd_v2` | Human (pending) |
| S5-R1 | Stale signal survives when a bar revision makes an already-published signal disappear | Next stage, by decision |
| S5-R2 | `scripts/replay_signals.py` behaviour change has no automated test | Next stage, by decision |

## Status lines that lag reality

`README.md`, `PHASE3_PLAN.md:3` and `PROJECT_STATE.md` under-describe S6/S7. This pack and the
evidence file are the accurate record; update the three files in the same commit that records the
S6 verdict, then regenerate the evidence so its hashes stay true.
