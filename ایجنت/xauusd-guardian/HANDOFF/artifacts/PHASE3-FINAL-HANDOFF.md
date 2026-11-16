> **UPDATE 2026-11-16 — supersedes section 0 below.**
>
> **`PHASE 3 CLOSED — INDEPENDENT PASS`**
>
> F1 was closed by the owner's option 3: the automated destructive reverse was **removed**
> (evert_migration refuses; emit_reverse_sql returns reviewed SQL that a human runs).
> The option-3 change passed an independent inspection; its two documentation findings were fixed
> in a docstring-only pass (AST unchanged) and confirmed by a further independent check
> (REPORT-CONFIRMATION-2.md): both digests efac4478…c39746, suite 297, compileall exit 0.
> The independent inspector answered **YES** to Definition-of-Done item 4. All twelve conditions
> are recorded below with their evidence. No commit, no push.
# PHASE 3 — FINAL HANDOFF (status: BLOCKED)

Author: Developer session (did not approve its own work)
Date: 2026-11-15
Companion: `REPORT-F1-INSPECTION.md` (independent inspector, verbatim copy), `EVIDENCE_MANIFEST.json`

## 0. Final status

**`PHASE 3 BLOCKED — ACCEPTANCE OR INDEPENDENCE NOT ESTABLISHED`**

S7 itself was independently passed (round 8). The blocker is residual **F1**, which the independent
F1 inspection returned **BLOCK** on: the ownership guarantee cannot be established with SQLite and
this architecture under the project's threat model. Definition of Done condition 4 is therefore
unmet, so Phase 3 cannot be closed.

## 1. Actual state (verified, not assumed)

| Item | Value |
|---|---|
| Project root | `C:\Users\icFixer.ir\AppData\Roaming\AutoClaw-oversea-official\accounts\41daec57d4756a03ca8efb2086ae29e4998b4a2ee8e2540c2e48ca7db7cf9831\projects\ایجنت\xauusd-guardian` |
| Branch | `fix/w1-timezone-validation` |
| HEAD | `e56b3a69b007e3c797a1a6952e6605d0e787935a` |
| Parent | `69e783dbdc3c259f62cb111c2c98c2448867a720` |
| Worktree | dirty by design: 5 modified + 14 untracked paths (S7 + F1 work). Nothing reset, cleaned or stashed. |
| Snapshot | `C:\GS7\snap-f1` — 178 files, byte copy, `.git/.venv/data` excluded |
| Commit / push | **none** |

## 2. Accepted stages (not re-audited)

Phase 2 ACCEPTED (A-08) · S1 PASS · S2 PASS (`ema_cross_v1`) · S3 PASS (replay `9a1dcfc8…`) ·
S4 PASS · S5 PASS (`9a3b53a`) · S6 PASS (`2e56ae7`) · W1 CLOSED. Suite at the S6/F1c baseline:
279 passed.

## 3. Findings inventory (reconciled against code and evidence)

| ID | Source | Finding | Classification | Status | Evidence |
|---|---|---|---|---|---|
| N1 | R4 report | `HANDOFF/MANIFEST.sha256` did not verify for 3 S7 reports | MUST-FIX | **FIXED** | manifest 16/16; `REPORT-S7-ROUND4.md` |
| N2 | R4 report | backticked / quoted-schema identifiers misparsed | MUST-FIX | **FIXED** | `test_apply_accepts_a_backticked_declaration`, round-8 |
| MF1 | R5 inspector | migration that creates nothing was recorded | MUST-FIX | **FIXED** | `_unattributed_create`, `test_apply_refuses_a_migration_that_creates_nothing` |
| MF2 | R5 inspector | `_declared_shape` on the old identifier dialect | MUST-FIX | **FIXED** | round-trip test with backticks |
| MF3 | R5 inspector | `ON DELETE CASCADE` deleted operator rows on revert | MUST-FIX | **FIXED** | cascade / SET NULL / SET DEFAULT tests |
| W2 | R5 inspector | quoted `"temp".` down-file bypassed the schema check | MUST-FIX (adopted) | **FIXED** | `test_down_script_rejects_a_quoted_non_main_schema` |
| R6-MF1 | R6 inspector (inferred) | single-quoted identifiers | diagnostics | **FIXED** | `test_single_quoted_identifier_is_refused_by_name` |
| R7-1..4 | R7 mandate | SET DEFAULT; VIEW/TRIGGER/TEMP scope; ATTACH coverage | MUST-FIX / scope | **FIXED / DECIDED** | `REPORT-S7-ROUND7.md` |
| **F1** | R8 inspector | a same-shape replacement table was dropped on revert | **MUST-FIX** | **OPEN — BLOCKED** | `REPORT-F1-INSPECTION.md` |
| F2 | R8 inspector | same-named `temp`/attached object blocks a legitimate revert | **ADVISORY** | open, accepted | inspector: fail-closed, atomic, misleading message |
| F3 | R8 inspector | DDL text inside a string literal attributed as a declared object | **ADVISORY** | open, accepted | inspector: fail-closed, whitelist not widened |

R8 verdict for S7 proper: **PASS** (0 must-fix at that time). The F1 finding was disclosed there as
"worth considering" with an explicit escalation condition; the user chose to remediate it.

## 4. F1 — technical ownership assessment

**What was built.** `schema_object_identity(version, kind, name, schema_rowid, rootpage,
sql_sha256, schema_version)`; the triple `(schema_rowid, rootpage, sql_sha256)` is measured at apply
inside the same transaction as the DDL and ledger, verified in `reversal_plan` before any DROP, and
deleted with the ledger rows on revert.

**What the independent inspector found.** `BLOCK`. Reproduced CASE A2 — operator drops
`idx_signal_runs_window`, drops `signals`, then re-creates `signals` with the migration's own DDL and
re-creates both indexes **in the original order**:

```
signals                 rec=(29, 32, sha256:2c42e3eb…)  live=(29, 32, 2c42e3eb…)  equal
signal_runs             rec=(27, 30, sha256:015831dc…)  live=(27, 30, 015831dc…)  equal
idx_signals_run         rec=(31, 34, sha256:4fc48c14…)  live=(31, 34, 4fc48c14…)  equal
idx_signal_runs_window  rec=(32, 35, sha256:1ca4a73e…)  live=(32, 35, 1ca4a73e…)  equal
revert(3) -> PROCEEDED, returned 3 ; ledger [1,2] ; operator row destroyed
```

The naive attack is refused only because `sqlite_master.rowid` happens to move (29 → 33); the shipped
test is green because of a 34↔35 page swap. Both are allocator artefacts, not a discriminator. The
report's guarantee #2 was therefore **false as written**.

**Why it cannot be fixed inside the database.** Every candidate signal
(`sqlite_master.rowid`, `rootpage`, DDL digest, column shape, `schema_version`) is a property of the
*replacement*, stored in the same file, readable and writable by anyone who can run `CREATE`. An
in-database token can detect **drift**, never **ownership**. The inspector also rejected the
object-attached marker (trigger/index created at apply) as an ownership proof: a replacement can
reproduce it, and adding undeclared objects conflicts with the project rule that provenance records
only what the migration declared.

**What would actually work** (needs an out-of-database trust anchor; none exists today):

1. append-only audit log **outside** the database (hash-chained file, written at apply), or
2. HMAC over the object token with a key the operator cannot read (key file with restrictive ACL / OS keystore), or
3. remove automated revert for tables: emit reviewed SQL for a human to run, with the reverse no longer a code path.

Options 1–2 are new mechanisms, not a "smallest fix", and each needs its own independent review.

## 5. F2 / F3 outcomes (independent classification)

| ID | Reproduction | Impact | Classification |
|---|---|---|---|
| F2 | attached DB with its own `signals`, or `CREATE TEMP TABLE signals`, makes `revert(3)` refuse `left objects behind ['side:signals']` | fail-closed, atomic rollback, nothing dropped; misleading message and an operational trap | **ADVISORY** |
| F3 | 0004 = `CREATE TABLE probe_sl (id TEXT);` + `INSERT … VALUES ('CREATE TABLE ghost');` → `did not create declared object(s) ['ghost']` | fail-closed; a valid migration is refused; reverse whitelist was not widened | **ADVISORY** |

Both were reviewed against their original acceptance criteria and are not must-fix: neither permits
an illegitimate operation.

## 6. Remediations and their regression tests

| Finding | Test(s) added | Pre-fix / post-fix |
|---|---|---|
| N2 | `test_apply_accepts_a_backticked_declaration`, `test_backticked_declaration_still_refuses_adoption`, `test_quoted_schema_prefix_creates_the_named_object` | failed on HEAD (`did not create declared object(s) ['main']`) → pass |
| MF1 | `test_apply_refuses_a_migration_that_creates_nothing`, `test_block_comment_cannot_hide_an_adoption` | no-op recorded → refused |
| MF2 | `test_backticked_declaration_round_trips` | apply-only → apply+revert |
| MF3 | `test_revert_refuses_a_cascading_child_table`, `test_revert_refuses_a_set_default_child_table` | child rows lost → refused |
| W2 | `test_down_script_rejects_a_quoted_non_main_schema` | schema rewritten → refused |
| R7 | `test_single_quoted_identifier_is_refused_by_name`, `test_create_view_is_refused`, `test_create_trigger_is_refused`, `test_revert_never_touches_an_attached_schema` | phantom `if` → statement named; VIEW/TRIGGER recorded → refused |
| F1 | `test_revert_refuses_a_same_shape_replacement`, `test_revert_refuses_a_byte_identical_replacement`, `test_reapply_records_a_fresh_identity` | same-shape replacement dropped → refused **for the cases tested**; CASE A2 still defeats it |

## 7. Test results (executed)

| Command | Exit | Result |
|---|---|---|
| `python -m pytest -q` (worktree and byte copy) | 0 | **295 passed, 0 failed, 0 errors, 0 skipped** (JUnit XML) |
| `python -m compileall -q src scripts tests` | 0 | clean |
| `probe_f1.py` (developer) | 0 | 9/9 — superseded by the inspector's CASE A2 |
| `probe_s7r4.py` / `probe_round5_cases.py` / `probe_round7.py` | 0 | 15/15 · 7/7 · 7/7 |
| Independent inspector suite | 0 | 295 / 0 / 0 / 0 |

## 8. Evidence and hash verification

| Artifact | SHA-256 |
|---|---|
| `src/guardian/storage/db.py` | `d836da1be944c472851075983731b6a92d5303f1e1f59a21890c53c9c46118f6` |
| `tests/unit/test_migration_reversal.py` | `3c5bd94b4a0cb92fa5a7d5934399e75feec776cac61fd5d73146db1e7815ccff` |
| `evidence/phase3-F1-20261115T192506Z.txt` | `6d9aec4ff12e6ea12127902fd54e8aefecf5e2deba0850b334d6c0a3761ea11f` |
| `HANDOFF/artifacts/REPORT-F1-INSPECTION.md` (inspector) | `39bcc6ffb13ac01332fa0fe17fd0f0e50723cba3f1f168d7497feff02324d191` |

Machine-readable inventory: `HANDOFF/EVIDENCE_MANIFEST.json`.

## 9. Discrepancies and limits found during this work

1. The developer's F1 report claimed index-bearing tables were protected; the inspector refuted it (CASE A2). The claim is withdrawn.
2. `schema_version` was recorded but deliberately not enforced: global, so any DDL blocked legitimate reverts.
3. F1's own regression test passes on a page-swap artefact and does not prove the guarantee.
4. Round-6's only must-fix was inferred and did not reproduce; recorded as such.
5. `REPORT-S7-ROUND6.md` is the developer's transcription: that inspector's budget expired before it wrote its report.
6. `MANIFEST.sha256` covers `HANDOFF/` only; `evidence/` is not in it (accepted, recorded).

## 10. Separate verdicts

| Role | Verdict |
|---|---|
| Developer (this session) | F1 remediation implemented and self-tested; **not** approved; known limitation since withdrawn as insufficient |
| Independent inspector (S7 round 8) | `S7 PASS` — 0 must-fix, F1 disclosed with escalation condition |
| Independent inspector (F1) | **`F1 BLOCK`** — ownership not established; in-database token is drift detection only |
| Final | **`PHASE 3 BLOCKED — ACCEPTANCE OR INDEPENDENCE NOT ESTABLISHED`** |

## 11. Safety confirmation

No commit, no push, no merge/amend/rebase/reset/clean/stash/cherry-pick, no deletion of existing
evidence. No network access. No MT5 connection, no broker interaction, no credentials, no orders,
no live trading. No Phase 4 work. No acceptance criterion weakened.

## 12. What is required to close Phase 3

1. Choose a trust anchor outside the database (audit log, keyed HMAC, or manual-SQL reverse) — §4.
2. Implement it as a scoped change with regression tests that fail on the current behaviour.
3. Independent inspection of that mechanism, including CASE A2.
4. Reconcile F2/F3 decisions (currently ADVISORY, accepted) and re-run DoD 1–12.
