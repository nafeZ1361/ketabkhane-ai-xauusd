# Phase 5 F1 — GitHub Actions Independent Inspector

Status: **IMPLEMENTED — FIRST EXECUTION / EVIDENCE VALIDATION PENDING**
Owner authorization: 2026-11-26
Scope: Replace the local Windows GuardianInspector account/session requirement for F1 only with an isolated GitHub Actions Inspector runtime. This does not authorize F2–F8, DEMO activation, order construction/submission, or LIVE trading.

## 1. Decision boundary

The owner authorized design and execution of a GitHub-native alternative to the local Inspector setup. The alternative changes the proof mechanism, not F1's technical contract requirements or its 10-point weight.

The new Inspector means an independent CI execution context, not a separate human reviewer or a second local Windows SID. Its independence is based on a separate ephemeral Windows runner/job, an immutable source artifact, a separately pinned harness commit, read-only GitHub token permissions, and no shared writable workspace with the freeze job.

## 2. Architecture

1. **Freeze job**
   - Runs on a GitHub-hosted Windows runner.
   - Checks out the exact triggering commit with persist-credentials disabled.
   - Archives only the Guardian project directory using git archive.
   - Computes SHA-256 and uploads the archive as a workflow artifact.
   - Performs no tests and has no repository write permission.

2. **Inspector job**
   - Runs as a separate job on a fresh windows-latest runner.
   - Downloads the frozen archive and verifies its SHA-256 against the freeze-job output.
   - Extracts a frozen snapshot and creates a separate writable test copy. Tests execute only against the copy; the frozen snapshot is not the test working directory.
   - Checks out the Inspector harness from immutable commit 203783d4909956f5b22b02a097eaa03766fc63b6 as an immutable commit in the implementation branch history. The workflow checks out this exact immutable commit, not the mutable branch tip or candidate working tree.
   - Uses contents: read and actions: read; checkout credentials are not persisted. No repository secrets or write token are passed to target tests.
   - Does not commit, push, merge, change refs, or modify repository settings.

3. **Hermetic Python environment**
   - Uses Windows x64 Python 3.11.8 in a fresh virtual environment.
   - Downloads only packages pinned in requirements-hashed.lock, with --require-hashes.
   - Requires exactly the eight wheel filenames and SHA-256 values in WHEELHOUSE.sha256.
   - Installs from that verified wheelhouse with --no-index --require-hashes; runs pip check.
   - The download phase requires network access to obtain packages; the installation phase is offline. Package hashes and exact wheel inventory are mandatory.

4. **Independent verification**
   - Focused F1 contract tests.
   - Full Guardian pytest suite.
   - compileall for src, scripts, and tests.
   - Pinned black-box harness covering strict schema/protocol, exact field sets, UTC timestamps, hostile mappings, JSON type/depth/cycle handling, deep immutability, serialization revalidation, and mutable timezone rejection.
   - Static boundary scan rejects MT5/order/network imports and symbols in the F1 contract module.
   - Mutation control deliberately reverses the schema-version predicate in a temporary copy; the independent probes must detect the mutant (non-zero result). The frozen source is never mutated.
   - SHA-256 manifest before/after inspection and archive digest after inspection must remain identical.

5. **Evidence**
   - Raw focused/full pytest logs, compile log, dependency download/install/check logs, machine-readable Inspector result, run summary, and SHA256SUMS.txt are uploaded as a workflow artifact.
   - Evidence is bound to the exact target commit and source archive digest.
   - A successful workflow is necessary but not sufficient until the artifact and the workflow/harness sources have been checked for the exact run.

## 3. Acceptance criteria

F1 earns 10/10 only when all are true on one exact target commit:

- Both freeze and Inspector jobs succeed.
- The Inspector verifies the exact source archive SHA-256.
- Frozen snapshot manifest before/after is identical and the archive digest remains unchanged.
- The eight wheel files match WHEELHOUSE.sha256 exactly; offline install and pip check succeed.
- Focused tests, full suite, and compileall exit 0.
- Black-box tests pass, static boundary scan has zero findings, and mutation control detects the deliberately broken schema predicate.
- Raw evidence artifact is present, complete, and every digest in its sidecar is recomputed and matched.
- The workflow and pinned harness commit used by that run are reviewed and recorded.

Any missing check, changed manifest, missing artifact, or mismatched hash means BLOCK; no partial points and no F2.

## 4. Security properties and limitations

**Established by this design:** separate ephemeral runner/job; no shared working directory; frozen artifact hash; separate writable test copy; separately pinned Inspector harness; read-only repository token permissions; no persisted checkout credentials; no secrets supplied to target tests; no CI write/merge capability.

**Not established:** a distinct local Windows account SID, a local interactive logon session, NTFS effective-access ACLs, or an external human reviewer's identity. The hosted runner's Windows service identity is not represented as equivalent to GuardianInspector. The Inspector job executes target code in a hosted runner with no secrets and no repository write token; this does not prove network isolation of the hosted runner.

The workflow and harness are version-controlled. A repository administrator can change workflow configuration or the pinned harness reference; the run is therefore reproducible and isolated, not cryptographically independent of repository administration. Any later change to the workflow, harness pin, lock files, or acceptance checks requires a new inspection run.

## 5. Scope control

- F1 only. The method does not change F1 deliverables, test obligations, or weight.
- F2–F8 remain NOT STARTED until F1 earns the full 10 points.
- PR #8 remains Draft and unmerged; this branch is separate.
- No local Windows account, ACL, Python installation, MT5, broker account, approval record, order path, or trading state is changed.
- No merge, branch protection change, or repository setting change is authorized by this plan.


The Inspector evidence artifact includes JUnit XML for focused and full-suite runs. The run summary records exact test, failure, error, and skipped counts; an exit code alone is not sufficient for acceptance.
