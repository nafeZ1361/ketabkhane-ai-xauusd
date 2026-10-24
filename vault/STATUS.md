# Project Status

- Stage: A-1 (MVP-1 core)
- Status: PASS (software gate), with open blockers for Phase B
- Updated: 2026-10-25
- Authoritative state: `docs/CURRENT_STATE.md`

## Delivered
- `src/xauusd_research/` - CSV schema, validation, three MA-crossover strategies,
  long-only backtester, report/manifest writers, CLI.
- `tests/` - 34 unittest tests plus a deterministic 500-candle fixture.
- `scripts/quality.py` - test run + line coverage gate (threshold 80%).
- `docs/` - charter, current state, open issues, decision log, evidence.

## Evidence
- Tests: 34 passed, 0 skipped.
- Coverage: 99.69% (`docs/evidence/coverage.md`).
- End-to-end + clean venv: `docs/evidence/e2e.md`.

## Boundaries
- Research/backtest only. No live orders, no MT5 connection.
- All results carry `NO_TRADING_COSTS` until a documented broker cost model exists.
- `legacy/source/` is a read-only archive and is never imported.