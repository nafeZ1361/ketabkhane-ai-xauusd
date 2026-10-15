# Current State — Single Source for Handoff

**As of:** 2026-10-15  
**Stage:** 0  
**Status:** BLOCKED  
**Authorized scope:** Stage 0 audit and documentation on `stage-0/draft-audit-plan` only.

## Goal
Build a reproducible and leakage-resistant XAUUSD ML research/backtest/paper-validation system. Correctness, safety, no-lookahead, reproducibility, and evidence take priority over profitability.

## Repository status
- New repo: `nafeZ1361/ketabkhane-ai-xauusd`, public.
- `main` baseline commit: `de4e4507ab12acb0db79bb88e649f7c3662de80a`.
- Work branch: `stage-0/draft-audit-plan`.
- No code or data copied from the old repository.
- No legacy scripts executed.
- Stage 1 has not started.

## Dataset — user-reported local facts
- Windows file: `XAUUSD_M1_201610030100_202610092354.csv` on Desktop.
- Size: 214,692,947 bytes.
- User-reported SHA-256: `E539F77788859C25F6D8B53606F89E7E3531AF1C46FF53207D9F0831DC2ACB9E`.
- User-reported total lines: 3,489,360, including one header; nominal data lines: 3,489,359. A second full sequential line-count pass completed in 15.733 seconds and returned the same count. This validates readability/count only, not row-level quality.
- Header fields: DATE, TIME, OPEN, HIGH, LOW, CLOSE, TICKVOL, VOL, SPREAD.
- First displayed row: 2016-10-03 01:00:00.
- Last displayed row: 2026-10-09 23:54:00.
- User says source is their Windows computer and MetaTrader 5 with AMarkets. Prior context says `AMarkets-Demo`; not yet independently verified against terminal/export metadata.
- These are command outputs provided by the user; assistant has not independently accessed the file.

## Confirmed static review findings
- Old repo reviewed at `nafeZ1361/golden-librarytallaii` main commit `36df7c9665ded188ab565d1fd4f25da63197c0f3`.
- `backtest/backtester.py`: MT5 calls and backtest at module import; reject direct reuse.
- `backtest/optimizer.py`: direct reuse rejected due MT5 coupling, broad exceptions, and selection-bias risk.
- `backtest/hashem_backtest.py` and `backtest/indicators.py`: deferred pending focused review.
- `backtest/run_csv_backtests.py`: not approved as-is; static review found possible look-ahead timing, unverified timezone assumptions, duplicate timestamp handling gaps, ambiguous OHLC stop/target paths, and zero-default costs.
- Static review only; no runtime test results exist.

## Current next action
Finish establishing a safe, efficient Stage 0 data-quality report from the local CSV using read-only streaming checks in PowerShell. The user has not yet provided the results of the full-file quality scan. Then record the report and distinguish genuine market-closure gaps from unexpected gaps. Do not ask for upload of the 205 MB CSV unless a smaller sample becomes essential.

## Stage 0 blockers
1. Full-file data-quality scan not yet reported: malformed rows, duplicate/out-of-order timestamps, OHLC violations, gaps, numeric validity, volume/spread summaries.
2. Source timezone and timestamp convention not verified.
3. Symbol specification and export method not verified from MT5 metadata.
4. Data usage and public redistribution permission not established.
5. No formal acceptance evidence package or independent Stage 0 review.
6. Old-code candidate review and reuse decision need final approval.

## Next-agent instruction
Continue Stage 0 only. If the user has not returned the scan output, guide them using the already provided read-only PowerShell script rather than asking broad questions. Do not repeat earlier questions. Keep `Stage status: BLOCKED` until evidence and explicit approval support PASS.
