# Phase 5 F1 — Developer Remediation Round 2

**Status:** Developer remediation complete; independent acceptance pending. This report is not
an Inspector review and does not award F1's 10 points.

## Target
- Repository: `nafeZ1361/ketabkhane-ai-xauusd`
- Branch: `work/guardian-phase5-entry-20261123`
- Code commit: `b546d402b3768ce7901723e4c2238ac21506e802`
- Parent: `4dbd827ed30b2e23cba8bb121729a67f24643301`

## Gap analysis and remediation
- Mutable `tzinfo` could return zero offset during validation, then a different offset during
  formatting. The helper now reads the offset once, requires exact `timedelta(0)`, and replaces
  the source tzinfo with `timezone.utc` before storing or serializing. Request and Response
  paths are both covered, including `object.__setattr__` injection before serialization.
- Arbitrary `Mapping` implementations could raise raw exceptions during copying. Top-level
  envelopes and payloads are copied through a guarded helper.
- Non-string field names are rejected before set/sort operations, closing mixed-key `TypeError`.
- Timestamp values require exact built-in `str`.
- `datetime.fromisoformat()` accepts arbitrary one-character separators. A shared parser now
  requires the ISO date-time separator `T` or `t` and rejects `X` or a space.

## Verification
- Guardian CI push run `45452257779`, job `138652205237`, Python 3.11.9:
  443 pytest progress dots to 100%; compileall step succeeded; job SUCCESS.
- Guardian CI pull-request run `45452270675`, job `138652252079`, Python 3.11.9:
  443 pytest progress dots to 100%; compileall step succeeded; job SUCCESS.
- CI & Evidence Gate run `45452270245`:
  Python 3.10.22: 120 passed, 0 failed, 0 errors; coverage 95.77%.
  Python 3.12.16: 120 passed, 0 failed, 0 errors; coverage 95.77%.
  Quality and encoding gates succeeded; artifacts uploaded.
- Mechanism-level Python probes reproduced the previous mutable-timezone, hostile-Mapping,
  mixed-key sorting and permissive ISO-separator behavior. These probes are not project-suite
  results.
- The full project suite was not run inside the owner's local Windows worktree during this turn.

## Scope and remaining gate
Only F1 contract code and tests changed. No MT5, order API, account data, credentials, ACL,
dependency, migration, DEMO activation or LIVE trading scope was added.
The current branch snapshot still requires independent read-only inspection by the actual
`GuardianInspector`. Developer changes and GitHub CI do not establish Inspector independence.
Until a fresh Inspector PASS on the final frozen commit, F1 remains 0/10 accepted points;
F2-F8 remain unstarted; PR #8 remains Draft/unmerged.

Evidence transcript: `evidence/phase5-F1-remediation-round2-20261124T1747Z.txt`
