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
- `docs/` - project records (transfer record, decisions)

## Agent entry points
Read `AGENTS.md` first, then `vault/STATUS.md` and `docs/`.

## Hard rules
Never commit CSV files, market data, secrets, or files larger than 5 MB.