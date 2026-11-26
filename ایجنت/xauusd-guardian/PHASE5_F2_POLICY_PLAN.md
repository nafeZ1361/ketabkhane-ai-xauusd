# Phase 5 F2 — Central Fail-Closed Policy

Status: **ACCEPTED — F2 12/12 (2026-11-27)**
Weight: **12 points**
Implementation branch: `work/guardian-phase5-f2-policy-20261127`
Accepted target commit: `a85bfc13ebb99ed034113540c7936ab57725341a`

## 1. Frozen F2 behavior

The central pure authorization decision point is `src/guardian/firewall/policy.py`.
It is deliberately deny-by-default and does not read approvals, broker state, account
data, environment variables, filesystem, or network.

- Only empty `POLICY_STATUS` may return ALLOW.
- Context must be the exact `PolicyContext` type, phase the exact integer `5`, and
  account mode the exact string `DEMO`.
- Wrong/missing context, wrong phase, non-DEMO mode, malformed/tampered request,
  unknown operation, or unexpected status payload returns DENY.
- DEMO execution/order operations (`DEMO_EXECUTION`, `ORDER_CHECK`, `ORDER_SEND`,
  `ORDER_MODIFY`, `ORDER_CLOSE`) are denied.
- LIVE operations are always denied.
- Account financial-data reads are denied because A-04 is not granted.
- A-09 remains restricted to the single post-Phase-11 Phase-12 validation and cannot
  authorize any Phase-5 operation.
- No order is constructed, submitted, or sent to MT5. F6 remains a separate,
  mandatory disabled-execution gate.
- Request state is serialized and reparsed before authorization to detect low-level
  frozen-dataclass mutation.

## 2. Independent Inspector architecture

Workflow: [45896771516](https://github.com/nafeZ1361/ketabkhane-ai-xauusd/actions/runs/45896771516)

- Freeze job `140172493274` archived only the Guardian project at the exact target commit.
- Inspector job `140172600121` ran on a separate fresh Windows hosted runner.
- The Inspector harness was checked out at immutable commit
  `0297a23415b15824f176067d355ba2c09aa95788`; it does not import candidate tests as
  its black-box oracle.
- Inspector identity `GuardianF2Inspector` used SID
  `S-1-5-21-3414932011-3134797172-3625386099-1003`, distinct from runner SID
  `S-1-5-21-3414932011-3134797172-3625386099-500`, and was verified non-admin.
- Harness, frozen snapshot, and evidence write probes were denied; test-copy and temp
  write probes succeeded.
- The Inspector child process received a minimal allowlisted environment; repository
  checkout credentials were not persisted and no repository write token or secrets
  were passed to target tests.
- Exactly eight wheel files matched `WHEELHOUSE.sha256`; offline installation used
  `--no-index --require-hashes`; `pip check` reported no broken requirements.
- The ephemeral Inspector account was removed after evidence upload.

## 3. Exact acceptance evidence

**Verdict: ACCEPTED — 12/12.** Target commit:
`a85bfc13ebb99ed034113540c7936ab57725341a`.

- Both Freeze and Inspector jobs: SUCCESS.
- Focused F2 tests: **28 passed**, zero failures/errors/skips; JUnit verified.
- Full Guardian suite: **471 passed**, zero failures/errors/skips; JUnit verified.
- `compileall`: exit 0.
- Independent black-box probes: **15/15 passed**.
- Static policy boundary findings: **0**.
- Negative-control mutation deliberately changed the execution denial to ALLOW;
  the independent black-box suite detected it with **7 expected failures** (15 tests,
  zero errors). The mutant existed only in a temporary copy.
- Frozen source manifest: **256 files, identical before/after**.
- Source TAR SHA-256 before/after: `30ee63f9be0b2615ceb9cf6ddc1bb83a8d461b1003546c42a6dde6121a743222`.
- Evidence artifact ID `15154865015`; downloaded ZIP SHA-256
  `fc7cf9a5273bcfbfc3e3b2c69d5eda59e9aa64d74a507857d2964d879f5bf0c8`.
- Frozen-source artifact ID `15154530758`; downloaded ZIP SHA-256
  `f74c2ee28cf823f99ac0c9d3a3253338f58019e75a099e4dfa1f05133abfddc1`.
- Evidence `SHA256SUMS.txt` contains 25 entries; every entry was independently
  recomputed and matched. Sidecar SHA-256:
  `4924c6e6fbf3c92988b63fdd3888c73a62be015033b1c9e4a41b9d37cdc21814`.
- Run summary SHA-256:
  `457843b2891b7b2119951fb04c2167c7b985f87edd93b0c62819718f3b43287d`.
- Inspector result SHA-256:
  `52862b525ddbd13aefa9a4ea4e3b1318dd5b581bc7c38ebaf459a6e68c7f85c8`.
- Focused JUnit SHA-256:
  `314dcceec90c5ed49753bed6d3c62664d65f369aff286fc25eb4fbe0c0637c48`.
- Full JUnit SHA-256:
  `bfd5523d4d3fcd0c1485f8da16cfbbff0568f8af06127ff0fc96d1d1d59c8a81`.
- Python: 3.11.8 x64 on Windows; `pip check` clean.
- Machine-readable Inspector verdict and workflow summary both report `PASS`.

## 4. Scope limitations and safety

This is the owner-authorized independent CI execution context, not an external human
reviewer and not proof of a GuardianInspector account or ACL on the owner's local
Windows machine. No network isolation of the hosted runner is claimed. The temporary
SID and ACLs existed only for this workflow run.

F2 grants no DEMO execution, LIVE trading, order construction/submission, broker
connectivity, financial account-data access, approval-file changes, or PR merge.
PR #8 remains Draft and unmerged. F3-F8 remain unstarted pending their own scope and
acceptance controls.
