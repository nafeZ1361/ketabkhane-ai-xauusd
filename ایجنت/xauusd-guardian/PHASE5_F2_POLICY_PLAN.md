# Phase 5 F2 — Central Fail-Closed Policy

Status: **IMPLEMENTED / CI PASS / INDEPENDENT INSPECTION PENDING**
Weight: **12 points; currently 0/12 accepted**
Implementation branch: `work/guardian-phase5-f2-policy-20261127`
Hardened candidate: `c35705ab1a3ee8bfc184eea3864402f98499da00`

## Scope

Implement one pure authorization decision point at `src/guardian/firewall/policy.py`.
The policy is deliberately deny-by-default. It is not an execution service and does not
read approval files, broker state, account data, environment variables, or the network.

## Frozen F2 behavior

- Only `POLICY_STATUS` with an empty payload may return ALLOW.
- The policy context must be the exact `PolicyContext` type, phase must be exact integer
  `5`, and account mode must be exact string `DEMO`.
- Wrong/missing context, wrong phase, non-DEMO mode, malformed request, unknown
  operation, or unexpected status payload returns DENY.
- All DEMO execution and order operations (`DEMO_EXECUTION`, `ORDER_CHECK`,
  `ORDER_SEND`, `ORDER_MODIFY`, `ORDER_CLOSE`) are denied.
- LIVE operations are always denied.
- Account financial-data reads are denied because A-04 is not granted.
- A-09 is restricted to the single post-Phase-11 Phase-12 validation. It cannot
  authorize any Phase-5 operation and is not consumed or interpreted by this module.
- No operation is constructed, submitted, or sent to MT5. F6 remains a separate,
  mandatory disabled-execution gate.

## Verification

Initial CI run on `54ecf9de7fe7944e90435a76415d3900ef3d69fa` completed SUCCESS (468 tests), then a security hardening change added mandatory request re-serialization/re-parsing before authorization and three adversarial mutation tests.

GitHub Actions `guardian-ci` on the hardened candidate
`c35705ab1a3ee8bfc184eea3864402f98499da00` completed SUCCESS:
- Python 3.11.9 hosted runner; dependency installation succeeded.
- Full Guardian suite: **471 tests passed**, no failures (pytest exit 0).
- `python -m compileall -q src scripts tests`: exit 0.
- Workflow: https://github.com/nafeZ1361/ketabkhane-ai-xauusd/actions/runs/45895338899

This is developer/CI regression evidence only. It is **not** the independent Inspector
verdict and earns no F2 points.

## Independent acceptance still required

A read-only Inspector must freeze the exact candidate commit and independently:
1. Verify snapshot/archive and evidence SHA-256 manifests before/after inspection.
2. Run focused F2 tests, full suite, and compileall; retain raw logs and exact exit codes.
3. Black-box probe every allowed and denied operation, malformed context, unknown
   operation, and A-09 scope non-transfer.
4. Run a negative-control mutation that makes an execution operation permissive; the
   independent probe must detect it.
5. Statically verify this module has no MT5, order construction/submission, account
   financial-data, I/O, or network path.
6. Confirm no F1 files, approvals, applied migrations, or unrelated project paths changed.

No self-approval. Until independent PASS, F2 remains 0/12 and Phase 5 remains 10/100.
