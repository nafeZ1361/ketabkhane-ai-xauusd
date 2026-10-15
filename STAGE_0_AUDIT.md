# Stage 0 — Initial Audit

**Status: BLOCKED — not approved for Stage 1**  
**Branch:** `stage-0/draft-audit-plan`  
**Audit date:** 2026-10-15  
**Scope:** GitHub inspection and documentation only. No code/data copied or executed.

## New repository facts
- Repository: `nafeZ1361/ketabkhane-ai-xauusd`
- Visibility: public; default branch: `main`
- Starting commit: `de4e4507ab12acb0db79bb88e649f7c3662de80a`
- Starting tree contained `README.md` only.
- The current `main` branch still points to the starting commit; Stage 0 documents exist only on the separate draft branch.

## Old repository backtest-folder inventory
Reference repository: `nafeZ1361/golden-librarytallaii`  
Reviewed source ref: `main` at `36df7c9665ded188ab565d1fd4f25da63197c0f3`.

Files found in `backtest/`:
- `backtester.py` — 1,998 bytes; blob `3df97e3150a35c2a2c326ab541d01a7be200d614`
- `hashem_backtest.py` — 59,642 bytes; blob `f5af0e80a12d16b4d0438a83e005089fc117f852`
- `indicators.py` — 36,855 bytes; blob `d658c9e292e942fe800fc3799036e557d36954ca`
- `optimizer.py` — 25,852 bytes; blob `aa2cc4a046d5a5366e89708387fee1f4ac2afa22`
- `run_csv_backtests.py` — 4,593 bytes; blob `ad589b6ee7826705ede276495e45abe279a5a574`

## Preliminary technical findings (static review only)
1. **`backtester.py` is not safe to import as a passive module:** it calls `mt5.initialize()` at module scope, requests candles, calculates signals, and runs a backtest immediately. Do not run it during Stage 0.
2. **`hashem_backtest.py` is tightly coupled to external services/libraries:** it imports MetaTrader5 and yfinance, and its backtest path attempts MT5 initialization. It is large and has broad exception/fallback behavior; it needs focused review before reuse.
3. **`optimizer.py` is high-risk for research validity:** it searches many parameter combinations, uses threads, initializes MT5 inside its backtest path, and contains broad exception handling that can hide failures. Results require strict out-of-sample validation to avoid selection bias.
4. **`indicators.py` is a large mixed indicator module:** it imports multiple third-party technical-analysis libraries and obtains data through `hashem_backtest` for many functions. Indicator formulas, warm-up behavior, and look-ahead safety have not been independently tested.
5. **`run_csv_backtests.py` is the most promising candidate for further review:** it accepts CSV input and uses a paper broker/historical replay, but it still imports legacy indicator code. Signal timing, candle alignment, costs, and reproducibility need tests before it can be accepted.
6. These are source-level observations, not a test report. No scripts were run and no claim of backtest correctness is made.

## Stage 0 checks still required
- [ ] Confirm dataset provenance, source, license, and redistribution permissions.
- [ ] Confirm MT5 broker/server, export method, timezone, timestamp convention, symbol specification, and coverage.
- [ ] Inspect dependencies and relevant source functions for each proposed backtest file.
- [ ] Verify no credentials, secrets, restricted data, or protected artifacts would be transferred.
- [ ] Define data-quality, no-lookahead, deterministic replay, and transaction-cost acceptance tests.
- [ ] Record candidate-by-candidate ACCEPT / REJECT / DEFER decisions.
- [ ] Review repository security settings and main-branch protection.
- [ ] Independent review and explicit human approval of Stage 0 evidence.

## Safety boundaries
- Research/backtest/paper validation only; not live trading.
- No real orders, broker credentials, autonomous trading, or production deployment.
- Do not execute the trading notebook or connect to MT5 during this audit.
- Do not copy code/data from the old repository without review and explicit approval.
- Do not change `main`, merge, or start Stage 1.
- UNKNOWN, INCOMPLETE, or FAIL is not PASS.

## Exit rule
Stage 0 remains BLOCKED until required checks have evidence, unresolved items are decided, and a human explicitly approves the exact scope. This document is an audit draft, not a PASS certificate.
