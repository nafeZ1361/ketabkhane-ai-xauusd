# Stage 0 — Initial Audit (Draft)

**Status: BLOCKED — not approved for Stage 1**  
**Branch:** `stage-0/draft-audit-plan`  
**Scope:** Documentation only. No code or data copied.

## Confirmed repository facts
- Repository: `nafeZ1361/ketabkhane-ai-xauusd`
- Visibility: public
- Default branch: `main`
- Starting commit inspected: `de4e4507ab12acb0db79bb88e649f7c3662de80a`
- The starting tree contained `README.md` only.
- Local files shown in the user's terminal are not yet part of this repository.

## Required checks before Stage 0 can pass
- [ ] Confirm the exact source and license/redistribution permission for the dataset.
- [ ] Confirm the intended MT5 broker/server and dataset export method.
- [ ] Record timezone, timestamp convention, symbol specification, and data coverage.
- [ ] Inspect the old repository's backtest folder only; document exact files considered and their dependencies.
- [ ] Decide explicitly which, if any, reviewed backtest files may be reused.
- [ ] Define Stage 0 acceptance tests and evidence locations.
- [ ] Review repository access/security settings and protect the main branch where supported.
- [ ] Human review and explicit approval of the completed evidence.

## Safety boundaries
- No real orders, broker credentials, autonomous trading, or production deployment.
- Do not run the trading notebook or connect to MT5 during this audit.
- Do not copy code or datasets from the old repository without review and explicit approval.
- Do not change `main`, merge, or push project code.
- Unknown, incomplete, or failed checks are not PASS.

## Exit rule
Stage 0 remains BLOCKED until applicable checks have evidence, unresolved items are decided, and a human explicitly approves the exact scope. This draft is not evidence that any check passed.
