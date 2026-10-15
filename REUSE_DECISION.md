# Old Repository Reuse Decision (Draft)

**Status: PENDING REVIEW**  
**New repository:** `nafeZ1361/ketabkhane-ai-xauusd`  
**Reference repository:** `nafeZ1361/golden-librarytallaii`

## Current decision
- The old repository is a reference for investigation, not a source to copy wholesale.
- Only the backtest folder may be considered for reuse, and only after file-level inspection and approval.
- No old-repository code, datasets, evidence, configurations, or other artifacts have been copied to this repository by this change.

## Required evidence for any proposed reuse
For each candidate file, record:
1. Exact path and source commit.
2. Purpose and dependencies.
3. Test/validation status and known defects.
4. Data, license, secret, and protected-artifact concerns.
5. Proposed destination and minimal change required.
6. Explicit human decision: ACCEPT, REJECT, or DEFER.

## Pending decisions
- [ ] Identify the exact backtest files to inspect.
- [ ] Review their imports, execution side effects, and test coverage.
- [ ] Verify licensing and provenance for any external code/data.
- [ ] Obtain explicit approval before copying any candidate file.

Until these items are completed, reuse is **NOT APPROVED**. This document records a draft decision policy, not approval to transfer files.
