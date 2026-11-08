# CHANGELOG

## [0.3.0] — 2026-11-05 — Phase 2: market data

### Added
- `contracts/market.py`: `MarketBar`, `MarketTick`, `Timeframe`, `DataQualityReport`, `TimeSyncResult`, `FeedRun`.
- `domain/market/`: `broker_clock` (EU DST server clock), `session` (exchange calendar), `quality` (bar/tick validation), `time_sync` (median + MAD).
- `adapters/mt5_market.py`: rates/ticks, numpy-free conversion, server-clock normalisation.
- `application/market_data_service.py`: per-timeframe runs, quota, manifests.
- `storage/market_store.py` + migration `0002_market_data.sql`.
- `scripts/collect.py`, `scripts/data_health.py`.
- 68 new tests (suite 93 → 161).

### Fixed during Phase 2
- Bar times were treated as UTC; MT5 reports **server** time. A fake 61-bar "gap" every day at the halt was the symptom.
- A single measured offset still mis-shifted pre-DST history; replaced with a modelled EU clock, cross-checked at attach.
- Audit F1: tick windows passed UTC to an API expecting server time (2 h shift) — now shifted and filtered on both sides.
- Audit F2: gap runs merged across closures (Friday→Sunday reported as a gap) — runs now flush at every closure.
- Remediation A1/A6: tick freshness uses the signed age (`|age| ≤ 5 s`, two-sided); the measured offset is evidence only and `set_server_offset` is removed.
- Remediation A2: the tick window is requested as a server-wall epoch (`utc + offset`); the old `datetime − offset` form asked 4 h early and its test asserted that value.
- Tick collection: `--ticks-start/--ticks-end` with strict validation, and `inserted=0` on a tick run is now `FAILED` instead of a silent `OK` (D-015).
- Run quarantine: `feed_runs.status='QUARANTINED'` with the previous status in `audit_events`; `health()`/`last_bar()` exclude it; `scripts/quarantine.py` applies, restores and reports. 24 new tests (174 → 198).

## [0.2.0] — 2026-11-04 — D-003 resolved: exact-identity resolver

### Added
- `guardian.domain.symbols.GoldExpectations` — versioned broker profile.
- Policy `xauusd_identity_v3`: exact alias identity + six-field metadata corroboration; returns `VERIFIED` / `NOT_FOUND` / `METADATA_MISMATCH` / `AMBIGUOUS` / `CONNECTION_FAILED`.
- `guardian.application.symbol_service.SymbolResolverService` — owns attach/verify/detach and converts terminal faults into `CONNECTION_FAILED`.
- `guardian.reporting.ranking.format_ranked` — single rendering path for ranked candidates.
- `[symbol_expectations]` config table, required when the identity policy is selected.
- 55 new tests (suite 38 → 93).

### Changed
- `SymbolResolution` carries `mismatches` and `observed` evidence; `ranked` is canonically `(score, name)`.
- `ResolutionStatus` gains `VERIFIED`, `METADATA_MISMATCH`, `CONNECTION_FAILED`; `RESOLVED` is retired as a distinct, non-permissive value (never an alias of `VERIFIED`).
- `configs/config.toml`: `symbol_policy = "xauusd_identity_v3"`.

### Fixed
- Audit finding 1: the `ranked` annotation claimed `(name, score)` while producers emit `(score, name)`, so `preflight.py` printed `top=6:XAUUSD.` — fields swapped. Annotation corrected, rendering centralised, regression tests added.
- Audit finding 2: the proposed Stage-C fallback would not have required `trade_mode == 4`; the fallback was removed entirely (no substitution allowed), so the gap cannot occur.

### Remediated after audit (F1–F4)
- **F1** `RESOLVED` was an enum alias of `VERIFIED`, so legacy scoring policies returned a permissive result and `preflight` printed `PASS` with no metadata corroboration. The alias is removed; `RESOLVED` is distinct and non-permissive.
- **F2** the alias list accepted bare `XAUUSD`. Config now pins `aliases = ["XAUUSD."]` and enforces `required_symbol_name`.
- **F3** account refusals were reported as symbol/connection failures with exit 1. Now a separate `account_gate` result with exit 2.
- **F4** policy registry duplicated across layers and `ValueError` masked as a terminal fault. Single-sourced from the domain; `ValueError` propagates.
- **F5/F6** (post-audit) `expected_company` was parsed but never enforced — now part of the account gate; `reject_on_mismatch = false` is now rejected instead of silently ignored.
- **F7/F8** (post-audit) a blank `expected_company` silently disabled that check — blank identity fields now fail config validation; the config→service wiring moved into `build_resolver_service` and is covered by two config→service wiring tests (not end-to-end gate tests — see PROJECT_STATE W3). Rechecked and closed by `reports/AUDIT-PHASE1-F7F8.md`.

## [0.1.0] — 2026-11-04 — Phase 1 Foundation

### Added
- Project skeleton (`src/` layout), truth files, `approvals/` registry.
- `guardian.contracts` — versioned contracts: `SymbolSpec`, `SignalCandidate`, `RiskDecision`, `SymbolResolution`, `ExecutionMode`, `TradeMode`.
- `guardian.domain.symbols` — spec-literal resolver `xauusd_strict_v1` plus `spot_metal_usd_v2`.
- `guardian.config` — strict TOML loader (`tomllib`), unknown keys rejected, `DEMO` execution mode rejected until A-05.
- `guardian.observability` — JSON logging with UTC timestamps and a redaction filter.
- `guardian.storage` — sqlite connection helper and hash-verified migration runner.
- `guardian.audit` — SHA-256 hashing and run manifests.
- `guardian.adapters.mt5_readonly` — the only module importing `MetaTrader5`; read-only attach, symbol table, minimal account identity (no balance/equity).
- `scripts/preflight.py` — read-only gate.
- Tests: symbol policy, config validation, redaction, migrations, boundary/AST scan.

### Fixed during Phase 1
- `scripts/preflight.py` imported `MetaTrader5` directly; import moved into the adapter (`package_version()`).
- Terminal path comparison used the exe path while MT5 reports the install directory — would have failed every attach.
- Boundary test used a substring heuristic; replaced with AST-based import detection.
