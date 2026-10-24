# ketabkhane-ai-xauusd

Auditable XAUUSD research, backtesting, and validation system.

## Layout
- `src/xauusd_research/` - MVP-1 core: schema, validation, strategies, backtest, report, CLI
- `tests/` - unit and end-to-end tests, plus the synthetic fixture
- `scripts/` - fixture generator and the quality gate
- `docs/` - governing documents and evidence
- `legacy/source/` - archived original library (quarantined, never imported)
- `data/` - local market data (gitignored; never commit CSV)
- `artifacts/` - generated outputs (gitignored)

## MVP-1 (v0.1.0-mvp)

No installation and no third-party dependency is required (stdlib only):

```powershell
python run_mvp.py run --csv tests/fixtures/synthetic_500.csv --out artifacts/mvp1_run
```

Outputs: `trades.csv`, `summary.json`, `manifest.json` (SHA-256 of inputs and outputs).
Every result carries the explicit label `NO_TRADING_COSTS` until a documented broker
cost model exists.

### Quality gate

```powershell
python scripts/quality.py
```

Runs the full test suite and measures line coverage of `src/xauusd_research`
(threshold 80%). Report: `docs/evidence/coverage.md`.

### Documents
- `docs/PROJECT_CHARTER.pdf` / `.md` - mother charter (authoritative PDF)
- `docs/CURRENT_STATE.md` - current phase, gate status, next allowed action
- `docs/OPEN_ISSUES.md` - open issues with IDs and closure conditions
- `docs/DECISION_LOG.md` - decisions, including pre-registered acceptance criteria
- `docs/TRANSFER_RECORD.md` - legacy import record and hashes
- `docs/evidence/` - test, coverage and end-to-end evidence

## Hard rules
Never commit CSV files, market data, secrets, or files larger than 5 MB.
`legacy/source/` is a read-only archive: never execute or import it.