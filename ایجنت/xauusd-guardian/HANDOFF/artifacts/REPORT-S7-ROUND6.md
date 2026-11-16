# Phase 3 — Gate S7, Round 6: Recorded Outcome

**This is not the reviewer's report.** The round-6 inspector returned its verdict and
findings in its answer, but its tool budget expired before it could write the full
report to disk. What follows is the implementer's transcription of that answer plus the
executed follow-up. Treat the reviewer's own wording as authoritative for the finding,
and this file as the record of what happened next.

Date: 2026-11-15
Tree reviewed: branch `fix/w1-timezone-validation`, committed HEAD `e56b3a6`, S7 work
uncommitted, 287 tests.

## 1. Verdict as returned

**BLOCK — 1 must-fix.**

> **MF1 — the adoption guard is blind to single-quoted identifiers.** `db.py:160-171`
> builds the declared-name set from `_CREATE_RE`, which does not match `'name'`;
> `_created_objects` returned `{}` for `CREATE TABLE 'probe_sq'`, while apply still
> commits measured provenance (`db.py:301-305`). `_existing_objects` therefore sees
> nothing to refuse, so `CREATE TABLE IF NOT EXISTS 'signals'` over an existing
> `signals` should adopt an operator table and record it as created.
>
> The reviewer marked this path **inferred, not executed** — its tool budget expired
> at the probe.

The same answer listed further gaps: `CREATE VIEW`/`TRIGGER` apply-and-record but never
revert; `ON DELETE SET DEFAULT` silently rewrites an operator child row; a `TEMP`
shadow yields a false "left objects behind"; a legacy DB without `schema_objects` leaks
a raw `OperationalError`; down-file drop order raises `OperationalError`; `ATTACH`
cases could not be tested.

## 2. Executed follow-up (implementer)

The inferred path was executed on the reviewed tree (`probes/probe_singlequote.py`,
copy `C:\GS7\r6`):

```
_IDENT matches single quotes?  False
_created_objects("CREATE TABLE IF NOT EXISTS 'probe_sq' (id TEXT);")  ->  {'if': 'table'}

A  single-quoted CREATE over an existing `signals`, alone
   err  = MigrationError: created no objects in main; refusing to record a migration
          that changed nothing
   hist = [1, 2, 3]   signals cols = ['operator_col']   (operator schema intact)

B  same, plus a real CREATE INDEX so the migration does create something
   err  = MigrationError: migration 0004_probe.sql did not create declared object(s) ['if'];
          refusing to record it
   hist = [1, 2, 3]   prov4 = ()   signals cols = ['operator_col']   rows = 1
```

**Result: the must-fix does not reproduce as a data-safety defect.** Neither variant is
recorded; the operator table and its row survive. The mechanism is that `_CREATE_RE`
backtracks past the unmatched quote and attributes the object named `if`, so the
post-apply `missing` check refuses the migration.

What remains is a **diagnostics** defect, not a safety one: the error names a phantom
object `if` instead of saying "this CREATE cannot be attributed". The same root cause
means a single-quoted declaration is unusable, which is the class N2/MF2 already
addressed for every other spelling.

## 3. Status

S7 is **not approved**. The last blocking finding does not reproduce, but the
implementer cannot discharge it — only an independent inspector can. Open items:

| # | Item | Severity |
|---|---|---|
| 1 | single-quoted identifiers: refused with a phantom `if` name; unusable spelling | diagnostics |
| 2 | `ON DELETE SET DEFAULT` is not in the FK pre-flight set (`{"CASCADE","SET NULL"}`) | silent child-row rewrite |
| 3 | `CREATE VIEW` / `CREATE TRIGGER` is attributed by no parser → applies, records, never reverts | apply/revert asymmetry |
| 4 | `ATTACH` has no in-repo test | test gap |

Items 2–4 were reported by round 6 and, unlike item 1, were not executed here.

## 4. Recommendation

A round 7 that (a) adds `SET DEFAULT` to the FK action set, (b) makes `_CREATE_RE`
fail closed on any `CREATE` it cannot attribute instead of backtracking to a bare word,
and (c) decides explicitly whether `VIEW`/`TRIGGER` are in scope — then re-executes
items 1–4 — is the shortest path to a defensible S7 PASS.
