# Phase 5 F1 — GuardianInspector Unblock and Reinspection Plan

Status: PLAN COMPLETE; LOCAL EXECUTION BLOCKED PENDING PREFLIGHT AND EXPLICIT ADMIN ACTION
Date: 2026-11-26
Scope: F1 evidence/independence only. No F2 work.
Remote reference: PR #8 head `58878fd86af837f37a4c6e1947d1d6f94eee64ff`.
Project authority: `PHASE5_PLAN.md`, `AGENTS.md`, `AI_WORK_PROTOCOL.md`.

## 1. Current disposition

F1 remains `INDEPENDENCE_NOT_ESTABLISHED`, 0/10 accepted points, until a genuinely independent Inspector completes the frozen-snapshot review. F2–F8 remain NOT STARTED.

The latest local checkpoint supplied for 2026-11-26 reports:
- Developer identity: `DESKTOP-2NLF7CP\icfixer.ir`, non-elevated.
- `GuardianInspector`: reported `Enabled=False`; a password was reportedly set on 2026-11-24. The current account state must be queried again on the target machine; neither value is assumed current.
- No second machine is currently available.
- A restricted token under the Developer identity is not an independent Inspector.
- Candidate worktree: `C:\GuardianF1\cand-f1cov-20261126`; reported 410 entries and one uncommitted test-file patch. The patch and snapshot must be re-hashed at execution time.
- Reported developer checks (72 focused, 449 full-suite, compileall exit 0, mutation probes 6/6) are developer evidence only, not Inspector acceptance.

These are owner-supplied local checkpoint details, not verified by GitHub. Do not infer that account enablement, ACL setup, or Inspector execution has occurred.

## 2. Stop-before-change preflight

Run from an elevated PowerShell session operated by the machine owner/admin. Do not run any account or ACL mutation until all checks below are captured.

1. Record UTC timestamp, machine name, current user SID, current logon ID, integrity/elevation state, and exact local project/candidate paths.
2. Query `GuardianInspector` existence, enabled state, SID, local group memberships, and profile path. Stop if missing, SID changed unexpectedly, or membership includes Administrators/other privileged groups.
3. Confirm the Developer and Inspector identities are distinct SIDs and will use distinct interactive logon sessions. A second process or restricted token under the Developer SID is insufficient.
4. Confirm the candidate path exists and is the intended frozen candidate. Record `git rev-parse HEAD`, `git status --porcelain`, candidate patch bytes/hash, and all candidate paths. Do not silently discard or commit the uncommitted test patch.
5. Check whether `C:\GuardianCustody` already exists. If it exists, do not reuse, overwrite, reset, or repair its ACL automatically; stop for owner review. Do not use `-Force` or recursive ACL replacement on an existing path.
6. Confirm the required Python 3.11 interpreter and all eight pinned wheelhouse artifacts are available and match the committed lock/hash records. Do not download packages or access the network.

Preflight failure means STOP with no mutations.

## 3. Dedicated Inspector identity

If the owner/admin authorizes local setup after preflight:

1. Enable the existing `GuardianInspector` account only after confirming its SID and intended ownership. Do not create a replacement account with a different SID without a new decision.
2. Set or rotate its password interactively using a secure prompt. Never place the password in a script, command-line argument, transcript, environment variable, Git file, or evidence.
3. Ensure the account is a standard user with only the approved `Users` membership; remove no group membership unless the owner/admin has inspected and approved the exact change.
4. Verify the actual Inspector logon by starting a separate interactive logon and capturing SID, logon ID, session ID, integrity level, group list, and privileges from inside that session.
5. If the account cannot be used in a separate session, stop. Do not substitute `runas /trustlevel`, impersonation, or a restricted Developer token as proof of independence.

The GitHub operator does not enable local accounts, reset passwords, or change local groups.

## 4. Create a new custody root safely

Only after preflight and explicit local admin approval:

1. Create `C:\GuardianCustody` only if it was confirmed absent. If creation fails or the path appears concurrently, stop.
2. Set a deliberate DACL on this new root: machine SYSTEM and local Administrators retain administrative control; the designated owner retains full control; `GuardianInspector` receives read/list/traverse only. Do not grant Modify/Write/Create/Delete/WRITE_DAC/WRITE_OWNER to Inspector.
3. Disable inherited broad access on the new root and verify the resulting ACL by SID, not display name. Do not change ACLs on the repository, user profile, Python installation, existing worktrees, or any pre-existing path.
4. Place a newly created snapshot beneath the custody root. Do not copy mutable source into a path writable by Inspector.
5. Apply and verify effective access across every descendant file and directory, not just the root. Record object count and any inheritance anomalies. Any unexpected broad ACE or write right is a blocker.

## 5. Freeze the exact candidate

1. Define the inspection target unambiguously: base commit SHA plus the exact uncommitted patch (if retained). The target is not PR #8 head unless its tree and patch are byte-identical.
2. Create a deterministic source archive from the chosen Git tree and apply the declared candidate patch in a separate staging area. Record archive SHA-256, patch SHA-256, sorted path/size/hash manifest, and file count.
3. Ensure the snapshot contains only the intended tracked project files and explicitly approved test inputs. Exclude `.git`, caches, virtual environments, databases, credentials, market data, and generated mutable outputs unless a pre-registered test requires a specific fixture.
4. Copy the frozen snapshot into the custody root, then make the Inspector's effective access read/list/traverse only.
5. Recompute the manifest after copy and compare every path, size, and SHA-256. Any difference is a hard stop.
6. Record the snapshot root and manifest location. Do not claim the snapshot is immutable solely because files have the Windows ReadOnly attribute.

## 6. Python and test execution boundary

1. Verify the full SHA-256 and version of the exact Python 3.11 interpreter used by the Inspector; record the resolved executable path and architecture.
2. Verify the exact eight wheelhouse files against the committed lock/hash manifest. Require exactly the expected filenames and hashes; reject extra, missing, renamed, or mismatched wheels.
3. Create a separate writable Inspector work directory outside the frozen snapshot, with only the minimum required write permission. The Inspector may copy the frozen source into this work directory for test execution; tests must never write into the custody snapshot.
4. Install only from the verified local wheelhouse with network access disabled and no system-site-packages. Capture the exact command, exit code, package list, and `pip check` result.
5. Run the pre-registered focused tests, full suite, compileall, and F1 black-box/mutation harness using exact commands from the frozen F1 acceptance checklist. Do not invent new acceptance criteria after observing results.
6. Capture raw stdout/stderr, JUnit or equivalent machine-readable result, harness JSON, and exit codes. Do not summarize away failures or skipped tests.

The existing report's 1 MB payload observation remains a disclosed F4 transport hardening item; it must not be silently reclassified as an F1 failure or treated as closed by this setup.

## 7. Inspector execution and independent verification

The Inspector must, from its own logon session:

1. Verify its own identity/SID/session and confirm it is not elevated.
2. Verify read/list access and deny results for create, append/write, rename, delete, ACL change, and ownership change on the frozen snapshot.
3. Recompute the manifest immediately before inspection.
4. Independently inspect the F1 contract implementation and tests; run the prescribed focused/full verification and black-box probes.
5. Recompute the manifest after inspection and require an exact before/after match.
6. Hash every raw output and create detached SHA-256 sidecars.
7. Produce an Inspector-authored report with PASS/BLOCK and explicit limitations. No Developer editing of the Inspector report or result JSON is permitted.

## 8. Acceptance decision

F1 earns 10/10 only if all PHASE5_PLAN.md criteria pass and the independent Inspector verdict is PASS on the exact frozen candidate, with identity, read-only enforcement, manifest stability, raw logs, and hashes verified.

Otherwise:
- identity/session not proven → `INDEPENDENCE_NOT_ESTABLISHED`;
- snapshot writable or manifest changed → BLOCK;
- test or contract failure → BLOCK;
- missing raw evidence or unrecomputed digest → evidence-integrity blocker;
- no F2 start and no partial F1 points.

## 9. Explicitly prohibited

No changes to the existing repository ACLs, user-profile ACLs, Python installation ACLs, broker configuration, MT5, account data, approvals, migrations, accepted evidence, trading code, or order path. No live/DEMO activation, order construction, order submission, network package installation, evidence rewrite, force-push, history rewrite, or PR merge.

## 10. Execution result template

Record a new timestamped report containing:
- preflight facts and exact commands;
- account SID/group/session facts before and after;
- every local path created and its initial existence result;
- DACL and effective-access results for every descendant;
- snapshot base SHA, patch SHA, archive SHA, manifest path/hash/count;
- Python executable path/version/architecture/full hash;
- exact eight wheel filenames and verified hashes;
- offline install and `pip check` outputs;
- focused/full tests, compileall, harness results and exit codes;
- Inspector identity/session proof;
- manifest before/after equality;
- raw artifact names and recomputed SHA-256 values;
- verdict, residuals, and what was not executed.

Do not fill this template with expected results. Only copy actual outputs after execution.
