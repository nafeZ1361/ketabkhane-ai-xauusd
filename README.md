# ketabkhane-ai-xauusd

Auditable XAUUSD research, backtesting, and validation system.

## Layout
- `src/xauusd_research/` - MVP-1 core: schema/TSV loader, timezone conversion, validation, strategies, backtest, streaming engine, report, CLI
- `tests/` - unit and end-to-end tests, plus the synthetic fixture
- `scripts/` - fixture generator, quality gate, dataset audit, parity check, full run
- `docs/` - governing documents and evidence
- `legacy/source/` - archived original library (quarantined, never imported)
- `data/` - local market data (gitignored; never commit CSV/TSV)
- `artifacts/` - generated outputs (gitignored)

## Quick start (no installation, stdlib only)

```powershell
python run_mvp.py run --csv tests/fixtures/synthetic_500.csv --out artifacts\test
```

Outputs: `trades.csv` (UTC timestamps), `summary.json`, `manifest.json` (SHA-256).
Every result carries `NO_TRADING_COSTS` until a documented broker cost model exists.

### Real MT5 export (TSV, `<DATE>` headers, Kyiv server time)

```powershell
python run_mvp.py run --csv "data\XAUUSD_M1_201610030100_202610092354.csv" --out artifacts\full --mode stream
```

- `--server-tz eu-dst` (default) converts Europe/Kyiv server time to UTC; alternatives: `fixed+2`, `fixed+3`, `utc`.
- `--mode auto` streams files larger than 64 MB; `stream` forces constant-memory processing (peak RSS ~21 MB on a 300k-row sample, independent of file size apart from the trade list).
- Spring-forward gaps and autumn ambiguous hours are rejected instead of silently guessed.

### Quality gate

```powershell
python scripts\quality.py
```

Runs the full test suite and measures line coverage of `src/xauusd_research` (threshold 80%).

### Documents
- `docs/PROJECT_CHARTER.pdf` / `.md` - mother charter (authoritative PDF)
- `docs/CURRENT_STATE.md` - phase, gate status, next allowed action
- `docs/OPEN_ISSUES.md` - open issues with IDs and closure conditions
- `docs/DECISION_LOG.md` - decisions, including pre-registered acceptance criteria
- `docs/evidence/` - audit, coverage, end-to-end, parity and full-run evidence

## Hard rules
Never commit CSV/TSV market data, secrets, or files larger than 5 MB (the synthetic
fixture under `tests/fixtures/` is the only committed data file).
`legacy/source/` is a read-only archive: never execute or import it.