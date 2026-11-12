# 02 — ROADMAP AND GATES

Derived from `PHASE3_PLAN.md` §6 and `PROJECT_STATE.md`. Nothing here adds a requirement that the
project has not already written down; where the source is silent, it says **TBD by human**.

## Phase 3 gate map (current phase)

| Gate | Meaning | Status | Evidence |
|---|---|---|---|
| S1 | look-ahead property test | PASS | suite |
| S2 | boundary / warmup tests | PASS | suite |
| S3 | replay determinism on stored bars (same digest twice) | PASS | `evidence/phase3-S3-*` |
| S4 | no `MetaTrader5` import outside adapters | PASS | `tests/security/test_boundaries.py` |
| S5 | suite green | PASS | 252/252 at S5, commit `9a3b53a` |
| S6 | migration 0003 additive and reversible | **PASS at the S6 inspection; F1 and F1b found at S7, both fixed** | `evidence/phase3-S6-20261112T191535Z.txt` |
| S7 | independent Inspector PASS on Phase 3 | **BLOCK ×2 (F1, F1b) → both fixed (274/274) → re-review pending** | `HANDOFF/artifacts/REPORT-S7*.md` |

### S7 — what the reviewer must establish

S7 is a **review gate, not an implementation stage**. It does not authorize new code.

1. Read `PHASE3_PLAN.md` §1–§7 and check the delivered tree against it, not against a summary.
2. Re-run the suite and `compileall` independently, and record exact commands, exit codes, counts.
3. Re-verify the S1–S6 evidence: digests reproduce, files still match, nothing was edited after
   the fact.
4. Confirm scope: only Phase 3 files changed; no Phase 4+ work; no MT5 connection; no orders; no
   new dependency; `main` and the parallel branch untouched; no commit/push performed.
5. Return exactly one verdict: `PASS` or `BLOCK`, with evidence. A PASS without executed evidence
   is invalid. Any unresolved destructive-risk finding is a `BLOCK`.
6. Write the verdict into a new file (never edit an existing evidence file) and update the phase
   status line **only after** a human accepts the verdict.

If S7 returns `BLOCK`: fix only the named defects, add focused tests, rerun, and hand back to the
same reviewer. Do not bundle unrelated improvements.

## After S7

Phase 4 is **not authorized**. Its shape is known only at the level below; the rest is TBD.

| Phase | Name | Status | Entry condition |
|---|---|---|---|
| 4 | Risk | NOT STARTED | S7 PASS **and** explicit human authorization **and** a written phase plan |
| 5 | Firewall | NOT STARTED | Phase 4 accepted; `firewall_process/` is the only future home of order APIs |
| 6 | Backtest | NOT STARTED | TBD by human |
| 7 | Monitoring | NOT STARTED | TBD by human |
| 8 | Integration | NOT STARTED | TBD by human |
| 9 | Independent audit | NOT STARTED | TBD by human |
| 10 | Remediation | NOT STARTED | Phase 9 findings |
| 11 | DEMO readiness | NOT STARTED | order submission is **not** authorized (approval A-05 never requested) |

Do not infer Phase 4 deliverables from the word "risk". Ask for the plan; write it as
`PHASE4_PLAN.md` and get it approved before writing code.

## Standard stage protocol (applies to every future stage)

A stage is done only when **all five** exist:

1. the smallest code change that satisfies the written requirement;
2. focused tests that fail when the protection is removed (a mutation probe, or an equivalent
   negative control);
3. the full suite green, with the exact commands and exit codes recorded;
4. a timestamped evidence file under `evidence/` plus its `.sha256` sidecar — produced by commands,
   never hand-written;
5. a `DECISIONS_LOG.md` entry if a contract, rule or stack changed.

And a stage closes only when an **independent** reviewer — one that did not write the change —
returns `PASS` with executed evidence.

## Never, at any stage

- live trading, a live flag, or any path that sends an order;
- reading balance/equity/margin/profit without approval A-04;
- importing `MetaTrader5` outside `src/guardian/adapters/`;
- editing an applied migration or an existing evidence file;
- deleting or weakening a test to make a gate green;
- rewriting history, force-pushing, or deleting the parallel branch.

## Where the ambiguity is (report it, do not resolve it alone)

- `PROJECT_STATE.md` lists phases 4–11 with names only. Acceptance criteria for 6–11 do not exist
  in the repository yet.
- S7 has no written template beyond `PHASE3_PLAN.md` §6; this pack adds the checklist above, which
  a human should confirm before the review is commissioned.
