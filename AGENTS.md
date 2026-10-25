# Agent Rules

0. Read `AI_MEMORY/00_START_HERE.md` first, then `docs/AI_HANDOFF.md`. `docs/PROJECT_CHARTER_V3.md` is the governing document.

1. Read `vault/STATUS.md`, `README.md`, and `docs/` before any work.
2. Never commit CSV files, market data, secrets, or any file larger than 5 MB.
3. `legacy/source/` is a quarantined, read-only archive: never execute or import
   it, never edit it in place. Create new code under `src/` instead.
4. Keep market data under `data/`; it is gitignored.
5. Update `vault/STATUS.md` when the stage or status changes.
6. Record material changes and evidence under `docs/`.