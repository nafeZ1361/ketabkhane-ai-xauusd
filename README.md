# ketabkhane-ai-xauusd

Auditable XAUUSD research, backtesting, and validation system.

## Layout
- `vault/STATUS.md` - current stage and status
- `config/risk.yaml` - risk limits
- `src/` - implementation of the new platform
- `tests/` - automated tests
- `artifacts/` - generated outputs (ignored by Git)
- `data/` - local market data (ignored by Git; never commit CSV)
- `legacy/source/` - original library, preserved verbatim for reference
- `legacy/README.md` - quarantine notice for legacy code
- `docs/` - project records and governing documents
  - `docs/PROJECT_CHARTER.pdf` - mother charter (authoritative, verbatim)
  - `docs/PROJECT_CHARTER.md` - machine-extracted text of the charter
  - `docs/TRANSFER_RECORD.md` - legacy import record and file hashes

## Agent entry points
Read `AGENTS.md` first, then `docs/PROJECT_CHARTER.md`, `vault/STATUS.md`.

## Hard rules
Never commit CSV files, market data, secrets, or files larger than 5 MB.