# XAUUSD Guardian

DEMO-only, offline-first XAUUSD research and execution system. Python 3.11, standard library first.

**LIVE TRADING IS UNSUPPORTED AND PROHIBITED.**

## Status

Phase 1 (Foundation) — see `PROJECT_STATE.md`. No market data, no strategy, no firewall yet.

## Layout

```text
xauusd-guardian/
├── AGENTS.md  PROJECT_STATE.md  DECISIONS_LOG.md  README.md  CHANGELOG.md
├── pyproject.toml  requirements.lock
├── configs/config.toml
├── approvals/            signed-off approval records (hash-chained)
├── src/guardian/
│   ├── contracts/        versioned data contracts (no I/O)
│   ├── domain/           pure logic: symbol resolution
│   ├── config/           TOML settings loader (strict, fail-closed)
│   ├── observability/    logging + redaction
│   ├── storage/          sqlite + migrations runner
│   ├── audit/            hashing + run manifests
│   └── adapters/         MT5 read-only adapter (only place importing MetaTrader5)
├── migrations/
├── scripts/preflight.py
├── tests/{unit,security}
├── data/ logs/ reports/ evidence/
```

## Install (project-local only)

```powershell
cd xauusd-guardian
C:\Python311\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
```

No global installs, no PATH changes. The AutoClaw bundled Python 3.13 is never used here.

## Run

```powershell
.\.venv\Scripts\python.exe -m pytest          # test suite
.\.venv\Scripts\python.exe scripts\preflight.py   # read-only environment gate
```

`preflight.py` is read-only: it attaches to the already-running terminal and never sends orders.

## Known blocker

On this broker the strict spec resolver (`xauusd_strict_v1`) returns `AMBIGUOUS` because four symbols tie at score 6. The evidence-based amendment `spot_metal_usd_v2` resolves `XAUUSD.` uniquely but is **PENDING_APPROVAL** (D-003) and is therefore not the default.
