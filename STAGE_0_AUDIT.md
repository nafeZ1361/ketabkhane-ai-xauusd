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

## Additional repository-record findings
- The old repository's `PROJECT_STATE.md` reports a locked dataset SHA256 prefix `a7d856d8…6414`, 480,087 rows, and a split-manifest mismatch recorded as GAP-001. These are claims in the source document, not independently verified against the CSV here.
- That same `PROJECT_STATE.md` records a PAPER-by-default mode but says LIVE can be enabled by `ENABLE_LIVE_TRADING=YES`. This is incompatible with the new project's no-live-trading boundary; do not transplant the old execution path or configuration.
- The old `PROJECT_STATE.md` records HEAD as `4448ff0`, while the inspected remote `main` is `36df7c9665ded188ab565d1fd4f25da63197c0f3`. The state document is stale relative to the inspected branch and must not be treated as authoritative current state.
- The old `DATA_FLOW.md` describes an MT5 M1 resampling path, but does not establish the provenance, permissions, timezone, or hash of the user's new-project CSV.

## Deeper static review of CSV replay path
Reviewed at source ref `golden-librarytallaii/main` commit `36df7c9665ded188ab565d1fd4f25da63197c0f3`; relevant blob SHAs:
- `backtest/run_csv_backtests.py`: `ad589b6ee7826705ede276495e45abe279a5a574`
- `module/backtest.py`: `469a74e1201cd912bad81fa0104b88a6066c0e76`
- `module/strategy_adapter.py`: `58984e11634c7ad8271f7ab74efc023a2027928f`
- `module/market_data.py`: `d06d0104df832b6af8a941e93a5e240a2c5b6ead`
- `module/paper.py`: `4877af18d4c07c18920ad3705611710d1e6d9a46`

**Blocking correctness findings:**
1. `HistoricalReplay.run` calls the strategy before adding the current candle to history, but the strategy receives the current candle separately. `CombinedVotingStrategy.__call__` evaluates indicators on `history + [candle]`, then emits a trade priced at `candle.open`. Indicators such as RSI/MACD/Supertrend use the current candle's close/high/low. This can make a decision using information from the candle's end and fill it at that same candle's open: a look-ahead/timing defect. It must be fixed and tested before this replay can support research conclusions.
2. The legacy strategy in `run_csv_backtests.py` calculates full-frame indicators first, then uses the current candle index to choose a signal while entering at that candle's open. Since the indicator values are derived from that candle's OHLC, this has the same potential look-ahead/timing defect.
3. `load_mt5_candles_csv` converts exported date/time values to UTC by attaching `timezone.utc`; it does not prove the original export timestamps were UTC. Source timezone must be established before this conversion is trusted.
4. `load_mt5_candles_csv` sorts the rows but does not reject duplicate timestamps, unlike the generic candle loader. Data integrity acceptance tests must cover duplicates and ordering.
5. `PaperBroker` simulates an OHLC path as open→high→low→close for bullish candles and open→low→high→close for bearish candles. This is deterministic, but intrabar order is assumed rather than observed; a bar touching both stop-loss and take-profit may have outcome ambiguity. Such bars need conservative handling or higher-resolution tick data.
6. The current runner sets default slippage and broker costs to zero unless configured elsewhere. A reported result without explicit spread/commission/slippage settings cannot be treated as cost-valid.

Static review only; these are source-level findings, not runtime test results. They make the CSV runner **not approved for research use as-is**.

## User-reported data origin (2026-10-15)
- The user states that the source data comes from their own Windows computer and MetaTrader 5 connected to AMarkets.
- Existing project context identifies the server as `AMarkets-Demo`; treat that as user-reported context until corroborated by the export or terminal metadata.
- This narrows the claimed origin but does **not** verify the exact CSV file, its SHA256, export settings, whether timestamps are broker-server time or UTC, symbol contract settings, completeness, or permission to redistribute the file publicly.
- Next evidence step: inspect the original CSV and a non-secret MT5 export/terminal metadata sample on the user's Windows machine. Do not request or copy passwords, account numbers, investor passwords, or broker credentials. No direct access to the user's Windows machine or MT5 session is available from this GitHub-only audit.

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
