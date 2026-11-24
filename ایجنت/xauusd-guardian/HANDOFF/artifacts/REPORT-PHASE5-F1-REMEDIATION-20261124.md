# Phase 5 F1 — Developer Remediation Report

**Status:** Developer remediation committed; independent acceptance pending. This report is
not an Inspector review and does not award F1's 10 points.

## Target
- Repository: `nafeZ1361/ketabkhane-ai-xauusd`
- Branch: `work/guardian-phase5-entry-20261123`
- Commit: `081e0303ef605a918b6c9104efa34fee8b17a5e8`
- Parent: `e0e7565535f3e80c1e28d8fe752b8c5397d11147`

## Defects closed by this remediation
1. `tzinfo` was consulted repeatedly. A mutable implementation could pass UTC validation and
   return a non-zero offset at serialization.
2. Arbitrary `Mapping` implementations could escape as raw exceptions during copying.
3. Mixed-type unknown field names could raise `TypeError` while sorting.
4. ISO timestamp parsing used `isinstance(str)` rather than requiring an exact built-in string.

## Changes
- `firewall.py`: snapshot the UTC offset exactly once; require `type(offset) is timedelta`
  and a zero offset; replace the original tzinfo with `timezone.utc` before storing.
- Both request and response constructors normalize timestamps.
- Serialization repeats validation and emits a canonical UTC timestamp.
- Top-level and payload Mapping inputs are copied through a fail-closed helper.
- Exact non-string field names are rejected before set/sort operations.
- Timestamp inputs require exact `str`; parse errors become `FirewallContractError`.
- `test_firewall_contracts.py`: new regression coverage for changing tzinfo, hostile mappings,
  mixed-type keys and low-level object-state injection.

## Verification
- Guardian CI, run `45451231751`, Python 3.11.9:
  `python -m pytest -q` reached 100% with 439 progress dots; run SUCCESS.
  `python -m compileall -q src scripts tests` completed; run SUCCESS.
- CI & Evidence Gate, run `45451244959`:
  Python 3.10.22: 120 passed, 0 failed, 0 errors; 95.77% coverage.
  Python 3.12.16: 120 passed, 0 failed, 0 errors; 95.77% coverage.
  Both quality gates and encoding guards succeeded; evidence artifacts uploaded.
- Mechanism-level local probes reproduced the old timezone serialization defect and raw
  `RuntimeError`/`TypeError` cases. These probes are not represented as full project tests.
- The full suite was not run in the owner's local Windows worktree during this turn.

## Scope and remaining gate
Only the two F1 source/test paths changed. No order API, MT5, account data, credentials,
ACL, dependency, migration or trading scope was added.
The exact commit must still receive a fresh read-only inspection by the independent
`GuardianInspector`. A Developer or CI result is not that inspection. Until independent
PASS, F1 remains unaccepted (0/10); F2-F8 remain unstarted; PR #8 remains Draft/unmerged.

Evidence transcript: `evidence/phase5-F1-remediation-20261124T1741Z.txt`
