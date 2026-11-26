# AI Work Protocol — XAUUSD Guardian

Status: CURRENT PROJECT-SPECIFIC OPERATING PROTOCOL
Scope: `ایجنت/xauusd-guardian/` only.
Updated: 2026-11-26
Baseline for this documentation branch: PR #8 head `58878fd86af837f37a4c6e1947d1d6f94eee64ff`.

## 1. Authority and precedence

1. Repository-root `AGENTS.md` governs repository-wide restrictions.
2. This directory's `AGENTS.md` governs Guardian-specific safety and implementation.
3. `PHASE5_PLAN.md`, `PROJECT_STATE.md`, and `DECISIONS_LOG.md` govern phase scope, status, and recorded decisions.
4. This file governs agent roles, evidence handling, and handoffs for current and future Guardian work.
5. `HANDOFF/00_READ_ME_FIRST.md`, `HANDOFF/01_STATE_SNAPSHOT.md`, `HANDOFF/02_ROADMAP.md`, and `HANDOFF/03_AGENT_PROTOCOL.md` contain historical or superseded guidance where they conflict with the current authorities above. In particular, do not use their old Phase 3 status, test counts, branch names, or next-stage instructions as current facts.

This protocol does not weaken any safety restriction, grant trading authority, or authorize changes outside this directory.

## 2. Verified remote baseline and current F1 disposition

- Repository: `nafeZ1361/ketabkhane-ai-xauusd`.
- PR #8: open, Draft, unmerged.
- PR #8 head at this protocol's preparation: `58878fd86af837f37a4c6e1947d1d6f94eee64ff`.
- Exact-head GitHub Actions observed SUCCESS for `guardian-ci` and `CI — Test & Evidence Gate`. CI success is not an independent Inspector verdict.
- The PR records an owner-supplied Inspector report for older target `e48729cbd92df86b63d3941d67fdcb8635210bf9`; its original report bytes and raw evidence were not available for recomputation. That report is not an automatic PASS for any later snapshot.
- The latest 2026-11-26 local remediation checkpoint supplied to the project records F1 as `INDEPENDENCE_NOT_ESTABLISHED`, 0/10 accepted points, with F2–F8 not started. That local checkpoint is not part of the remote PR snapshot and must be independently reproduced before being treated as verified repository evidence.
- The candidate worktree reported locally as `C:\GuardianF1\cand-f1cov-20261126` is not the same thing as PR #8 head. It was reported as a 410-entry candidate snapshot with a one-file uncommitted test patch. Do not conflate its manifest with the PR tree or claim a commit SHA for an uncommitted candidate.

## 3. Mandatory role separation

### Developer
- May inspect and modify only the explicitly authorized worktree and paths.
- Must record exact baseline commit, candidate patch digest, file manifest, commands, exit codes, test counts, and residuals.
- Must not create or edit Inspector verdicts, Inspector result files, or acceptance records.
- Must stop on unexplained test failures, scope conflicts, or safety-boundary changes.

### Independent Inspector
- Must execute in a genuinely separate Windows logon/session and process context under the dedicated standard `GuardianInspector` identity.
- A restricted token, impersonation label, second terminal under the Developer identity, or Developer-authored report is not independent identity.
- Must not be an administrator and must not belong to privileged groups beyond the explicitly approved standard `Users` membership.
- Must receive a frozen snapshot that is readable but not writable by the Inspector identity.
- Must independently reproduce the manifest before and after inspection and perform effective-access/write-denial/probes.
- Must produce its own raw result, test logs, manifest, and report. The Developer may register the result but may not alter its verdict.

If any identity, session, snapshot immutability, or raw-evidence condition is unavailable, verdict is `INDEPENDENCE_NOT_ESTABLISHED`; award zero gate points. Do not self-approve.

## 4. Snapshot and evidence contract

For every inspection, register all of the following:

1. Target identity: source commit SHA, candidate patch SHA-256 (if uncommitted), archive SHA-256, and a sorted per-file manifest.
2. Snapshot location and ownership; exact ACL/SID data; effective-access results for every descendant.
3. Manifest digest before and after Inspector execution; they must match.
4. Inspector identity SID, logon/session identifier, integrity level, group membership, and privilege list, captured from the actual Inspector process.
5. Explicit read/list success and write-class denial probes (create, append/write, rename, delete, ACL change, ownership change) against the snapshot.
6. Test command, environment/interpreter identity, exact pytest counts, exit code, compileall command and exit code, and relevant harness output.
7. Raw evidence files and detached SHA-256 sidecars. Recompute every digest from the supplied bytes; a digest written in prose is not verification.
8. Scope, exclusions, failures, false positives, residuals, and exact verdict.

Never edit an existing evidence file. Add a new timestamped artifact. Do not place credentials, passwords, account identifiers, or secrets in evidence.

## 5. Required execution sequence

`reconcile baseline → freeze candidate → establish independent identity → enforce snapshot read-only → Inspector reproduces manifest → Inspector runs checks → Inspector reproduces manifest again → verify raw evidence hashes → independent verdict → owner-facing report`

No later gate may start before the previous gate's independent PASS is recorded. In Phase 5, F2–F8 remain NOT STARTED until F1 earns its full 10 points.

## 6. Git and change controls

- Work on a dedicated task branch, never directly on `main` or the existing PR head branch.
- Branch creation, commit, and push require explicit owner authorization. The owner authorized those three actions for the documentation-only task branch `docs/guardianinspector-f1-readiness-20261126`.
- That authorization does not include merge, PR promotion, changing PR #8 metadata, changing branch protection, force-push, history rewrite, deleting branches/worktrees, or modifying unrelated files.
- Use explicit file paths; never stage all files blindly.
- Recheck branch, parent, changed paths, and resulting commit after every write.
- Keep PR #8 Draft and unmerged unless separately authorized.

## 7. Trading and system safety

- DEMO remains disabled; no MT5 connection, order construction, order submission, account financial-field access, LIVE mode, or broker credential access is authorized by this protocol.
- Do not modify approvals, migrations, trading code, broker/account configuration, ACLs, local Windows accounts, or local machine state as part of a documentation-only GitHub task.
- No new dependency, destructive operation, evidence rewrite, or scope expansion without separate authorization.

## 8. Verification limits and reporting

GitHub inspection can verify committed content, commit ancestry, PR metadata, and CI results. It cannot establish the current state of a local Windows account, local logon session, effective NTFS ACLs, or an uncommitted worktree. Those require execution on the target Windows machine.

A report must separate:
- verified remote facts;
- owner-supplied local claims not yet reproduced;
- actions performed in this session;
- checks not executable from GitHub;
- blockers and next entry condition.

Never convert a CI pass, a documentation update, or an Inspector report transcription into an independent inspection PASS.