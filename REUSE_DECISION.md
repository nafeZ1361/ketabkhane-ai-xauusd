# Old Repository Reuse Decision

**Status: PENDING REVIEW — no files approved for transfer**  
**Reference repository:** `nafeZ1361/golden-librarytallaii`  
**Reviewed ref:** `main` at `36df7c9665ded188ab565d1fd4f25da63197c0f3`

## Candidate-by-candidate decision

| Source file | Preliminary finding | Decision |
|---|---|---|
| `backtest/backtester.py` | Runs MT5 initialization, data retrieval, signal generation, and backtest at import time. Not safe as a reusable library module. | **REJECT for direct reuse**; only consider extracting pure logic after separate review. |
| `backtest/hashem_backtest.py` | Large, coupled to MT5/yfinance and has broad exception/fallback behavior. Correctness and isolation not established. | **DEFER**; do not copy as-is. |
| `backtest/indicators.py` | Large collection of indicators with third-party dependencies and legacy data-access coupling. No independent leakage/warm-up tests reviewed. | **DEFER**; identify and test individual pure functions first. |
| `backtest/optimizer.py` | Large parameter search, MT5 coupling, broad exception handling, and selection-bias risk. | **REJECT for direct reuse**; redesign only after a validated baseline exists. |
| `backtest/run_csv_backtests.py` | CSV-oriented replay using `HistoricalReplay` and `PaperBroker`; still imports legacy indicators and signal timing/cost assumptions are unverified. | **DEFER; best candidate for deeper review**, not approved to copy. |

## Review evidence
The five files were read through GitHub at the ref above. Static review only; no code was executed. File blob SHAs and preliminary findings are recorded in `STAGE_0_AUDIT.md`.

## Rules for any future candidate
For each proposed reuse, record exact source commit/path, purpose, dependencies, execution side effects, tests, known defects, provenance/license concerns, destination, and the smallest possible change. Require no-lookahead tests and deterministic replay evidence where relevant.

No code, datasets, configurations, or evidence from the old repository have been copied by this work. No candidate is approved for transfer. Human approval is required before any copy or adaptation.
