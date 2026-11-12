# 04 — PROMPT TEMPLATES

Copy, fill the bracketed parts, paste. Each template already carries the prohibitions, so you do not
have to re-explain the project to a fresh model.

---

## 1. S7 — independent inspection (read-only)

> You are an independent Inspector on `nafeZ1361/ketabkhane-ai-xauusd`, project `ایجنت/xauusd-guardian`.
> You did not write this code. Work read-only: do not modify, stage, commit, push, fetch, merge or
> rebase anything, and never connect to MetaTrader5.
>
> Task: decide whether Phase 3 gate **S7** passes. Requirement: an independent PASS over Phase 3,
> judged against `PHASE3_PLAN.md` §1–§7 and `PROJECT_STATE.md`, not against any summary.
>
> Do:
> 1. Record `git rev-parse HEAD`, branch, and `git status --porcelain`. HEAD must be
>    `9a3b53af95267c6ecaeca6b567006f671786ecd7`; `main` must be `1dad958…`; the parallel branch
>    `fix/xauusd-guardian-w1-timezone` must be untouched at `76d468e…`.
> 2. Re-run independently: `C:\Python311\python.exe -m pytest -q`, the targeted
>    `tests/unit/test_migration_reversal.py`, and `-m compileall -q src scripts tests`. Record exact
>    commands, exit codes, counts.
> 3. Verify S1–S6 evidence reproduces: `evidence/phase3-S6-20261109T173019Z.txt` and its sidecar;
>    hashes must match the files on disk now. Note that `…170723Z.txt` is superseded.
> 4. Check scope: no Phase 4 work, no MT5 import outside `adapters/`, no order API, no new
>    dependency, no commit/push, no unrelated file changed.
> 5. Perform at least one mutation/negative control of your own, in a throwaway copy outside the
>    repository, proving a claimed protection is load-bearing.
>
> Deliverable: a new file `evidence/PHASE3-S7-<UTCstamp>.md` (never edit an existing evidence file)
> and an answer of at most 900 characters with exactly one verdict — `PASS` or `BLOCK` — plus the
> three strongest confirmations, any BLOCK reason, and the limits of what you could not verify.
> A PASS without executed evidence is invalid.

---

## 2. Commit a change set (only with explicit human authorization)

> Already done for S6: commit `2e56ae7` on `fix/w1-timezone-validation`. This template is kept for the
> next authorized change set.
>
> Authorized action: create **one** commit on `fix/w1-timezone-validation` containing exactly the
> change set below. Do not push. Do not amend or reset. Do not `git add -A`.
>
> Add exactly these paths (relative to `ایجنت/xauusd-guardian/`):
> `src/guardian/storage/db.py`, `tests/unit/test_migration_reversal.py`,
> `migrations/rollback/0003_signals.down.sql`, `DECISIONS_LOG.md`, `PHASE3_PLAN.md`,
> `PROJECT_STATE.md`.
> Do **not** add `evidence/phase3-S5-202608…txt` (untracked by design) unless I say so separately.
>
> Message: `feat(s6): reversible migration 0003 with guarded reversal`
>
> Then, and only if I ask: also add `evidence/phase3-S6-<…>.txt` + `.sha256` and `HANDOFF/`.
> Verify with `git show --stat HEAD` and `git status --porcelain`; report both.

---

## 3. Fix one named residual (R-item)

> Defect: **R<n> — <one-line title>** from `HANDOFF/01_STATE_SNAPSHOT.md`.
> Fix only this. Do not touch anything else.
>
> Requirements: smallest possible diff; add or adjust a focused test that fails without the fix;
> run the targeted test and the full suite; record commands, exit codes and counts; add a new
> evidence file with digests; if a contract changed, add a `DECISIONS_LOG.md` entry.
> Do not edit applied migrations or existing evidence. Do not commit or push.
> If the fix turns out to need more than one module, stop and report why.

---

## 4. Phase 4 — planning only (requires human authorization first)

> Phase 4 is **not** authorized. Do not write code.
> Produce `PHASE4_PLAN.md` only: scope, non-goals, contracts, data flow, failure modes, acceptance
> criteria, test strategy, evidence plan, stop conditions, and an explicit list of approvals needed.
> Read `PHASE3_PLAN.md` as the shape to imitate, `DECISIONS_LOG.md` for constraints (no balance/
> equity, no orders, adapters-only MT5), and `HANDOFF/02_ROADMAP.md` for the gate structure.
> End with the questions a human must answer before implementation starts.

---

## 5. Cheap resume (new agent, minimal tokens)

> Repo `nafeZ1361/ketabkhane-ai-xauusd`, project `ایجنت/xauusd-guardian`. Read
> `HANDOFF/00_READ_ME_FIRST.md` and `HANDOFF/01_STATE_SNAPSHOT.md` only. Then answer in ≤10 lines:
> current gate, uncommitted change set, next authorized action, and the first file you would open
> for task `<task>`. Do not read source yet.

---

## 6. Hand this stage back to a human

> Write a handoff note of at most 400 words: what changed, what is proven with which evidence file,
> what remains open (R-items, decisions), what is explicitly not done (S7/Phase 4), and the one
> command a human should run to convince themselves. Reference paths, not prose.
