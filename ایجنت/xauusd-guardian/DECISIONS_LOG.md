# DECISIONS_LOG

Append-only. One entry per decision that changes a contract, a rule, or the stack. Newest last.

---

## D-001 — Approved runtime stack
**Status:** ACCEPTED (2026-11-04, A-02)
**Decision:** Python 3.11.8 x64 from `C:\Python311\python.exe`, isolated venv at `.venv\`, dependencies pinned in `requirements.lock`. AutoClaw's bundled 3.13 interpreter is excluded from the trading core.
**Reason:** Phase 0 evidence — MetaTrader5 5.0.6231 present only on 3.11; the vendor 3.13 interpreter lives inside the app install and can be replaced by updates.
**Rollback:** delete `.venv\`; no system state touched.

## D-002 — Terminal binding
**Status:** ACCEPTED
**Decision:** `mt5.initialize(path=<approved exe>)` always; assert `terminal_info().path` equals the approved directory; refuse to start otherwise. Never use the last-used terminal, never depend on `APPDATA`.
**Reason:** three MT5 installations exist on this host; `APPDATA` is absent in this execution environment while attach still works with an explicit path (verified 2026-11-04).
**Rollback:** config-only change (`configs/config.toml`).

## D-003 — Symbol resolution policy
**Status:** **ACCEPTED AND IMPLEMENTED** (2026-11-04, Phase 1 authorization)
**Decision:** `xauusd_identity_v3` is the default policy.
- **Stage A — exact identity:** the symbol name must equal one entry of a configurable alias list (`[symbol_expectations].aliases`, default `XAUUSD` / `XAUUSD.`), case-insensitive, no substring matching, no scoring.
- **Stage B — corroboration:** live metadata must match the versioned broker profile — path token `Spot Metals`, `currency_profit` = account currency, `contract_size` 100, `tick_size` 0.01, `digits` 2, `trade_mode` 4. Any deviation returns `METADATA_MISMATCH` listing every `(field, expected, actual)`.
- **No substitution.** A missing or invalid `XAUUSD.` returns `NOT_FOUND` / `METADATA_MISMATCH`; the resolver never falls back to another symbol.
**Deviation from proposal P1:** the Stage-C fallback scoring was **dropped**, because the implementation authorization states "Do not guess another symbol if `XAUUSD.` is missing or invalid". Recorded here rather than silently omitted.
**Reason:** the §7 weighted score cannot separate the target from two US equities on this broker (4-way tie at 6; see `reports/D-003_symbol_investigation.md`).
**Effect:** preflight now returns `VERIFIED` on `XAUUSD.`; the strict policy is retained for replay and still blocks — that is expected, not a regression.
**Rollback:** set `symbol_policy = "xauusd_strict_v1"` (restores the blocking behaviour).

## D-011 — Phase 2 market data
**Status:** ACCEPTED AND IMPLEMENTED (2026-11-05, Phase 2 authorization)
**Decisions:**
1. **Broker clock is modelled, not measured per timestamp.** MT5 stores bar/tick times in server time; the server is UTC+2 winter / UTC+3 summer (EU DST). A single measured offset mis-shifts half the year by an hour, which reads as a fake daily gap. The measured offset at attach must agree with the model (±90 s) or the run blocks.
2. **Session calendar is exchange-anchored** (America/New_York, DST rule in code): Sunday 18:00 open, Friday 17:00 close, Mon–Thu 17:00–18:00 halt. Verified against live data: M1 stops after 21:55Z and resumes 23:00Z in winter, exactly as modelled.
3. **Bars are revision-safe**: current row updated only after the prior version is written to `bar_revisions`.
4. **Ticks dedupe on `(symbol, time_msc, bid, ask)`** and are quota-bounded per chunk (refuse, never evict).
5. **Resolution floor**: a series whose density falls below `min_bars_per_day` of the session calendar is quarantined (`DAILY_RESOLUTION_DETECTED`), never stored as intraday.
6. **Dependency direction**: `contracts.market` holds shapes; `domain.market.*` holds rules; the adapter is the only MT5 importer.
**Rollback:** drop `data/guardian.sqlite3*`, revert migration 0002 + new modules.

## D-012 — Data root stays in-project
**Status:** ACCEPTED (2026-11-05)
**Decision:** `data_root = "data"` (in-project) rather than the recommended `D:`. With the 2 GB tick quota and 6 h window cap, C: (15.8 GB free) is sufficient, and provenance stays inside the repository.
**Deviation:** Q2 recommendation was D:. Recorded here instead of silently changed.
**Rollback:** change one config key.

## D-009 — Ranked display ordering
**Status:** ACCEPTED AND IMPLEMENTED (2026-11-04)
**Decision:** `ranked` entries are canonically `(score, name)` (`contracts.schemas.RankedSymbol`), rendering goes through `guardian.reporting.ranking.format_ranked`, and regression tests assert `"GOLD.:6"` (name first, score second).
**Reason:** audit finding 1 — the annotation said `(str, int)` while producers emitted `(int, str)`, so `preflight.py` printed `top=6:XAUUSD.` with the fields swapped in the very line meant to evidence the tie.
**Rollback:** revert the two files; tests would fail immediately.

## D-010 — Audit remediation (F1–F4)
**Status:** ACCEPTED AND IMPLEMENTED (2026-11-04) — remediation cycle 1 of max 3
**Decision:**
1. `ResolutionStatus.RESOLVED` is **no longer an alias of `VERIFIED`**. It keeps its own value and is non-permissive, so the legacy scoring policies can never open the gate (F1).
2. New `GoldExpectations.required_symbol_name`; shipped config pins `aliases = ["XAUUSD."]` and `required_symbol_name = "XAUUSD."`. A widened alias list can therefore never silently accept a different instrument (F2).
3. Account/server/currency refusals are reported as `account_gate_failed` → `BLOCKED` / exit 2, distinct from a real connection fault (F3).
4. The policy registry is single-sourced from the domain layer, and `ValueError` is re-raised instead of being masked as `CONNECTION_FAILED` (F4).
5. Audit F5/F6: `expected_company` is enforced in the account gate; `reject_on_mismatch` must be `true` (fail-closed is not configurable).
6. Audit F7/F8: blank account identity fields are rejected by the loader; service construction is centralised in `build_resolver_service` and covered by end-to-end tests.
**Reason:** independent audit `reports/AUDIT-PHASE1-D003.md` — 2 must-fix, 2 worth-considering. F1 was a regression introduced by this implementation; F2 was a latent gap in the proposed design.
**Evidence:** suite 88 passed; preflight `PASS` with `VERIFIED XAUUSD.` (17:46Z).
**Rollback:** revert the commit-level diff; the new tests fail on the old behaviour.

## D-004 — Dependency policy
**Status:** ACCEPTED
**Decision:** stdlib-first. Allowed now: `MetaTrader5==5.0.6231`, `pytest`. `PyYAML` and `pydantic` rejected — `tomllib` (stdlib) covers config, `dataclasses` covers validation.
**Reason:** ~1.2 GB free RAM, low-power CPU, offline-first requirement.
**Rollback:** add packages only with justification + approval.

## D-005 — No packaging install
**Status:** ACCEPTED
**Decision:** `src/` layout without an editable install; pytest resolves the package through `pythonpath = ["src"]`.
**Reason:** avoids a build backend dependency and keeps the environment reproducible offline.
**Rollback:** add `[build-system]` and install editable.

## D-006 — Storage
**Status:** ACCEPTED
**Decision:** `sqlite3` with a file-based migration runner (`migrations/NNNN_*.sql`, recorded with version + SHA-256 in `schema_migrations`).
**Reason:** reproducibility, tamper evidence, zero dependencies.
**Rollback:** drop the DB file; migrations are additive.

## D-008 — Interim offline venv
**Status:** ACCEPTED_PROVISIONAL (2026-11-04)
**Decision:** `.venv` is created from `C:\Python311\python.exe` with `--system-site-packages` and inherits `MetaTrader5==5.0.6231` and `pytest==9.2.0` from the approved base interpreter.
**Reason:** `pip install` failed — the configured index `https://mirror.runflare.com/pypi/simple` is unreachable (`ProxyError: Cannot connect to proxy`), and no local wheel cache exists. Nothing was installed globally; the venv itself is still prefix-isolated (`sys.prefix != sys.base_prefix`).
**Consequence:** the environment is not hermetic yet. A base-interpreter package upgrade would silently change the venv.
**Exit criteria:** before Phase 5, either restore index access or build a local wheelhouse, then recreate `.venv` hermetically and re-run the full suite.
**Rollback:** delete `.venv\` and recreate.

## D-007 — Execution modes
**Status:** ACCEPTED
**Decision:** `DRY_RUN` (default) and `SIMULATED` allowed in Phase 1–4. `DEMO` is defined but rejected by the config loader until approval A-05 exists. No live mode is defined anywhere.
**Rollback:** config-only.

## D-013 — Tick freshness is a two-sided age; one clock authority
**Status:** ACCEPTED AND IMPLEMENTED (2026-11-05, Phase 2 remediation A1/A6)
**Decision:**
1. `tick_age_seconds` returns the **signed age** `(now + model) - tick.time`: positive = the tick is older than server-now, negative = it is stamped ahead of it. Freshness is `abs(age) <= 5 s` and `tick.time > 0`. The previous `0..5` window measured a *lead*, so every tick ≥1 s old was rejected and quiet runs fell into `clock_unverified`.
2. The modelled `BrokerClock` (EU DST) is the **only** offset source for conversion. A measured offset is evidence (`time_sync`), never a conversion input: one constant offset would shift history across a DST switch by an hour. `set_server_offset` and `measured_offset_s` are removed; the service records the measurement instead.
**Reason:** `reports/AUDIT-PHASE2-CLOCK.md` A1, A6. Live probe 2026-11-05T15:22Z measured `age = -2 s` on every sample — accepted by the new rule, rejected by the old one.
**Rollback:** restore `0 <= age <= 5` and the measured-offset branch (not recommended).

## D-014 — Tick window request is a server-wall epoch
**Status:** ACCEPTED AND IMPLEMENTED (2026-11-05, A2 fix, authorized in-session by the human)
**Decision:** `ticks()` passes `int(start_utc.timestamp()) + BrokerClock.offset_for(start_utc)`. The terminal reads an integer as a **server wall-clock** epoch and subtracts its own offset; a naive datetime is resolved through the host zone first and double-shifts the window.
**Reason:** live probe 2026-11-05T16:52Z — `datetime.fromtimestamp(start − 7200)` returned the first tick 4 h early; `start + 7200` returned it at 0 s. The previous test asserted the wrong value, so the suite could not catch it (`AUDIT-PHASE2-CLOCK` A2).
**Effect:** the UTC-side filter no longer hides a 4 h over-request; at peak rates the 200 k cap now begins at the intended window instead of exhausting 4 h early.
**Rollback:** restore `datetime.fromtimestamp(start − offset)` (not recommended).

## D-015 — Absolute tick windows, isolated evidence DB, enforced quarantine
**Status:** ACCEPTED AND IMPLEMENTED (2026-11-05, Phase A/B of the master prompt)
**Decision:**
1. `collect.py` gains `--ticks-start` / `--ticks-end` (zone-carrying ISO-8601). Explicit bounds are never mixed with `--ticks-minutes`, are never replaced by `now()`, and reversed, empty or negative windows are refused *before* any file is opened.
2. A tick run that inserts zero rows is `FAILED` (`inserted_zero:no_new_rows`), never a silent `OK`.
3. Recollection targets a separate evidence database (`--db`), so `PRIMARY KEY (symbol, time_msc, bid, ask)` cannot swallow a replay.
4. Quarantine lives on `feed_runs.status = 'QUARANTINED'` with the previous status stored in `audit_events`; `health()` and `last_bar()` exclude quarantined runs; `scripts/quarantine.py apply|restore|status` restores exactly. `quarantined_series` stays series-only — its `timeframe` is `NOT NULL` and cannot describe a tick run.
**Reason:** the three verified blockers from `reports/PHASE2-REMEDIATION-REPORT.md`; the old quarantine was write-only.
**Effect:** replay run `3087c765…` reproduces the original digest `799bc8c7…` exactly; the original 7 840 rows are unchanged and the run is quarantined pending human review.
**Rollback:** drop the evidence DB; `python scripts/quarantine.py restore --run-id e01f4fe7…`.

## D-016 — Signal persistence: exact Decimal, bar-derived identity, fail-closed conflicts
**Status:** IMPLEMENTED (2026-11-08, Phase 3 / S5); pending independent Inspector sign-off
**Decision:**
1. `migrations/0003_signals.sql` is additive only and adds `signals` (PRIMARY KEY `(symbol, timeframe, bar_time_utc, strategy_id)`) and `signal_runs`. Applied migrations 0001/0002 are untouched.
2. `signals.strength` is stored as `TEXT`, not `REAL`. The contract requires a finite `Decimal`; a REAL column would round-trip through binary floating point and silently change the replay digest. Bars stay `REAL` because they arrive from the broker as floats.
3. `signal_runs` carries `symbol` in addition to `strategy_id`/`timeframe`, so a run that emits zero signals is still attributable to one instrument.
4. The run window and `run_id` are derived from the bars alone: `from_utc` = first bar time, `to_utc` = last bar close, `run_id` = `run_` + SHA-256 over strategy, version, timeframe, symbol, window, bar count and bar digest. Wall-clock `now` never enters the identity, so re-running later over the same closed bars yields the same `run_id` and the same digest.
5. Closed-bar filtering is explicit in the service (`bar_time_utc + timeframe.minutes <= now`), because `mt5_market.rates()` starts at position 0 and therefore stores the forming bar. `ema_cross.evaluate()` keeps its own forming-bar refusal as defence in depth; the service must never hand it a forming bar.
6. Every signal read excludes quarantined feed runs (`run_id NOT IN (SELECT run_id FROM feed_runs WHERE status = 'QUARANTINED')`), including `scripts/replay_signals.py`, which previously read bars unfiltered.
7. A stored signal that disagrees with a recomputation (`direction`, `strength` or `reason_code`) raises `SignalError` and rolls the transaction back. The service never overwrites a published signal; resolving a revised bar is a human decision.
8. S6 reversibility is implemented in `db.py`. `reversal_plan` resolves and validates the reverse before anything runs, and `revert_migration` executes it inside one explicit `BEGIN IMMEDIATE ... COMMIT`, so either the schema is fully reversed and the ledger says so, or nothing happened. A reverse is refused unless every statement is a plain `DROP TABLE`/`DROP INDEX` of an object created by the paired forward migration (parsed from the `CREATE ...` statements in that file), unless each such table's live columns still match the declared ones, and unless, after execution, none of those objects remains in `sqlite_master` — that post-condition is what catches an incomplete down file and rolls it back. It also refuses an unapplied version, a later version still applied, a forward file whose hash no longer matches the ledger, and a missing or ambiguous down file. Down files live in `migrations/rollback/NNNN_name.down.sql`; the dotted name cannot match the forward discovery pattern, so a reverse is never applied as a forward step. Reverses are DROP-only by policy: a future migration whose reverse needs `ALTER` requires a new decision, not a wider whitelist. The earlier statement that reversal was a manual `DROP TABLE IF EXISTS` step is superseded.
**Reason:** S5 of `PHASE3_PLAN.md`; independent Inspector review of the plan returned four must-fix defects (forming bar, silent `INSERT OR IGNORE`, unfiltered replay read, missing decision record), all incorporated before implementation.
**Effect:** 252/252 tests pass, up from 220; suite exit 0; `compileall` exit 0. Five existing assertions that pinned the migration inventory were updated to include `0003_signals.sql`; no assertion was weakened or removed.
**Rollback:** `DROP TABLE IF EXISTS signals; DROP TABLE IF EXISTS signal_runs;` and delete `0003_signals.sql` from any database that never applied it.