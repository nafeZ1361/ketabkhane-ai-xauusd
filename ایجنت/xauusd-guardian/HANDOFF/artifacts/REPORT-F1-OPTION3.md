# F1 — Option 3: automated destructive reverse removed

Developer record. Not an approval. A fresh independent inspection is required.

Date: 2026-11-15 · Branch `fix/w1-timezone-validation` · HEAD `e56b3a6` (S7 work uncommitted)

## 1. Decision

The independent F1 inspection returned **BLOCK**: no in-database evidence can prove object
ownership, because a dropped object can be re-created with the same `sqlite_master.rowid`,
`rootpage` and DDL, all of which the operator controls. The owner therefore chose **option 3**:
remove the automated destructive reverse and emit reviewed SQL for a human.

This is not a workaround for F1 — it removes the class of harm. The tool no longer drops anything,
so it cannot drop a replacement.

## 2. What changed

| | Before | After |
|---|---|---|
| `revert_migration(...)` | validated, then executed `DROP … ; DELETE …` in a transaction | **raises** `MigrationError("automated reversal has been removed…")`; holds no DDL |
| new `emit_reverse_sql(...)` | — | runs every existing precondition through `reversal_plan`, then returns a self-contained script: `BEGIN IMMEDIATE;` + `main`-qualified `DROP`s + the three ledger `DELETE`s + `COMMIT;` |
| `_verify_reversal` | post-condition after executing drops | **removed** — there is no execution to verify |
| completeness | ensured at runtime by the post-condition | ensured at emit time: a down script that leaves an owned object behind is refused (`… leaves objects behind: [...]`), where an index is covered when its table is dropped or when it no longer exists |

Preconditions still enforced before a script is emitted: provenance present, identity token match,
declared-shape match, foreign-key dependents (`CASCADE`/`SET NULL`/`SET DEFAULT`), and the down-script
whitelist (plain `DROP TABLE|INDEX`, `main` only).

## 3. Guarantees after the change

1. The library contains no statement that drops a table or index. `revert_migration` cannot destroy
   anything, regardless of database state.
2. `emit_reverse_sql` either returns a complete, `main`-qualified, transactional script or raises —
   it never mutates the database (verified: schema and ledger identical before and after).
3. A human decides whether to run the script. That is the only path to a reverse.
4. F1's harm is closed at the tool level: even the CASE A2 state (byte-identical re-creation that
   restores rowid/rootpage/DDL) now produces a script, not a deletion. A human reviewing that script
   sees `DROP TABLE main."signals"` and the row count question is theirs to answer.

## 4. Honest limits

- The emitted script is still destructive **when run**. Ownership is no longer asserted by the tool;
  it is asserted by the human who reviews and runs it.
- `emit_reverse_sql` will still emit a script for a state the identity token cannot distinguish
  (CASE A2). It does not claim the object is the original; it reports the script the ledger implies.
- A reviewer who wants the tool to refuse that state needs an out-of-database trust anchor, which
  option 3 deliberately avoids.

## 5. Tests

Suite: **297 passed, 0 failed, 0 errors, 0 skipped** (was 295; two added, and the operator stand-in
helper keeps the existing coverage meaningful).

New: `test_the_library_never_executes_destructive_ddl`, `test_emitted_script_is_self_contained_and_inert`.
The test suite now does what a human would: `emit_reverse_sql` → review assertions → `executescript`
with an explicit rollback on failure.

Probe (5/5): library refuses · emit is inert · script is main-qualified and transactional · script
works when run · re-apply still works.

## 6. Hashes

- `src/guardian/storage/db.py` `efac447834c1538c16e42c86c1464c0d24e8f4c1fca394c91282ed7f78c39746`
  (the value at the time option 3 was implemented was `51aa633d…`; a later documentation-only
  pass changed the digest while the AST stayed identical, as the final inspection confirms)
- `tests/unit/test_migration_reversal.py` `b77d59d6de247127174c0ac3e38058e255a69f6b7923f39362a1f3fd576f8874`
- evidence `evidence/phase3-F1-OPT3-20261115T201338Z.txt` (with `.sha256`)

## 7. Status

F1 as a *tool-side destructive path*: **closed by removal**. F1 as an *ownership proof*: **not
achieved, and no longer required** by this architecture. Phase 3 closure still requires the
independent inspection of this change and re-checking Definition of Done 1–12.
