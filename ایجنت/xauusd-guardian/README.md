# XAUUSD Guardian

DEMO-only, offline-first XAUUSD research and execution system. Python 3.11, standard library first.

**LIVE TRADING IS UNSUPPORTED AND PROHIBITED.**

## Status

As of 2026-11-21: Phase 3 ACCEPTED (D-022), Phase 4 Risk ACCEPTED (D-024), and Phase 4b Monte Carlo ACCEPTED (D-027). Phase 5 Firewall is PRE-REGISTERED under D-028 but BLOCKED on the D-008 hermetic-environment entry gate; no F1–F8 implementation gate has started. Phases 6–11 remain NOT STARTED and require their own approved plans. DEMO execution remains disabled; A-05 is absent. LIVE trading is unsupported and prohibited.

**Any AI agent starting work here: read `AGENTS.md`, `HANDOFF/00_READ_ME_FIRST.md`, `PROJECT_STATE.md`, `DECISIONS_LOG.md`, and `PHASE5_PLAN.md`.** `PROJECT_STATE.md` and the append-only `DECISIONS_LOG.md` are the status authorities; older handoff snapshots are historical context only.

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
