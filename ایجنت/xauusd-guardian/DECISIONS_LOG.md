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
8. S6 reversibility is implemented in `db.py` as four layers. (a) `apply_migrations` refuses to record a migration whose declared objects already exist, comparing names case-insensitively and accepting every identifier spelling SQLite accepts (bare, double-quoted, bracketed, backticked, schema-qualified). (b) Each apply measures what it actually created — the difference in `main.sqlite_master` before and after — and records it in `schema_objects`, so the ledger stores provenance rather than intent. (c) `reversal_plan` refuses when provenance is missing, a later version is still applied, or the forward file changed; it requires exactly one strict `NNNN_name.down.sql`, and allows only `DROP TABLE`/`DROP INDEX` of objects recorded as created by that migration, targeting `main`. (d) `revert_migration` runs those drops, each qualified with `main.`, inside one `BEGIN IMMEDIATE ... COMMIT`, then requires that no recorded object survives in any schema (main, temp, attached) and that no object the migration did not create disappeared from any schema; otherwise the whole reverse rolls back. A database applied before provenance tracking existed (commits `2e56ae7`, `3deaf8c`) has no provenance and is refused a reverse: audit or rebuild it instead. Reverses are DROP-only by policy; a reverse whose logic needs `ALTER` requires a new decision.
- **Correction (2026-11-19):** layer (d) is **withdrawn**. The automated reverse was removed (owner option 3, 2026-11-16): `revert_migration` raises `MigrationError`, and `emit_reverse_sql` validates a reverse and returns the script a human runs. The in-database ownership claim was refuted by CASE A2 (`REPORT-F1-INSPECTION.md`). See D-019.
**Reason:** S5 of `PHASE3_PLAN.md`; independent Inspector review of the plan returned four must-fix defects (forming bar, silent `INSERT OR IGNORE`, unfiltered replay read, missing decision record), all incorporated before implementation.
**Effect:** 252/252 tests passed at the time of S5, up from 220; suite exit 0; `compileall` exit 0. Five existing assertions that pinned the migration inventory were updated to include `0003_signals.sql`; no assertion was weakened or removed.
**Rollback:** `DROP TABLE IF EXISTS signals; DROP TABLE IF EXISTS signal_runs;` and delete `0003_signals.sql` from any database that never applied it.
## D-017 - 2026-11-16 - Keep idx_bars_tf_time; defer the composite index

- **Decision:** keep `idx_bars_tf_time (timeframe, time_utc)`; do not add a
  `(symbol, timeframe, time_utc)` index in this phase.
- **Reason:** the project is single-symbol (XAUUSD.), so `symbol` is constant and the
  existing index is effectively equivalent. Adding migration 0004 would change the applied
  version in every database and invalidate 30 exact-version assertions, for a marginal gain
  measured at noise level.
- **Revisit:** if the project becomes multi-symbol, add `0004_bars_symbol_index.sql` with
  `DROP INDEX idx_bars_tf_time; CREATE INDEX idx_bars_symbol_tf_time ON bars (symbol,
  timeframe, time_utc);` and update the version assertions.
## D-018 - 2026-11-17 - ML edge test on XAUUSD M1: no exploitable edge found

- **Test:** walk-forward (70/30 chronological), features from past bars only, labels
  = sign of forward return, cost 2 bps round trip; 300k M1 bars ending 2026-10.
- **Models:** logistic (AUC .508/.511), decision tree depth 4 (.510/.507),
  HistGradientBoosting (.509/.522) for horizons 15 and 60 minutes.
- **Result:** AUC ~0.51, i.e. barely above chance. Best net per trade: tree +0.0022%
  (h=15, n=2174) and +0.0101% (h=60, n=4366) - inside sampling noise and not
  consistent across horizons or models. Always-long is negative after cost.
- **Conclusion:** these features and this labelling do not produce a tradeable edge on
  this data. Recorded as a negative result; do not present the backtest as profitable.
- **Correction (2026-11-17):** the sentence "Always-long is negative after cost" is
  misleading and is withdrawn: the reference line is the mean of overlapping forward
  returns over every test bar, which is neither buy-and-hold nor a tradeable strategy.
  Also "walk-forward" is inaccurate: this was a single 70/30 holdout, not sequential
  folds. See STAGE-A-AUDIT.md D9/D10.
- **Revisit only with:** different label (triple-barrier), microstructure features, or a
  strictly out-of-sample period that was never inspected.

## D-019 — Test collection scoped to this project; stale reverse documentation corrected (2026-11-19)

- **Problem 1 (blocking).** `python -m pytest` aborted at collection (exit 2):
  `tests/unit/test_stageB_leakage.py` and `tests/unit/test_research_features.py`, added by the
  research commits `c192c16`/`1d489dd`, import `pandas`/`sklearn` (banned here by AGENTS rule 7)
  and execute `scripts/research_edge.py` at import time. The Guardian suite could not run at all.
- **Fix.** `tests/conftest.py` now declares `collect_ignore` for those two paths. The two files
  are byte-identical to HEAD; only collection is scoped. No test was deleted or weakened and
  Guardian's own 300 tests still run. **Owner decision still required:** relocate them to the
  research project.
- **Problem 2 (documentation, W2 from `REPORT-OPT3-INSPECTION.md`).** Five places still described
  the removed executed-reverse model. Corrected to emit-terms: `PHASE3_PLAN.md` §5,
  `migrations/0003_signals.sql` header, `migrations/rollback/0003_signals.down.sql` header,
  `tests/unit/test_migration_reversal.py` docstring, and the correction note on the S6 entry above.
  No behaviour change; no DDL touched.
- **W3 (fixed 2026-11-19).** The three `DELETE FROM schema_*` lines in the emitted script are now
  `DELETE FROM main.schema_*`; regression test `test_emitted_script_targets_main_despite_a_temp_homonym`
  proves both directions. Verified as advisory only (`evidence/phase3-w3-20261119T203654Z.txt`).
- **Verification.** `.venv\Scripts\python.exe -m pytest` → 300 passed, exit 0;
  `-m compileall -q src scripts tests` → exit 0. Raw output:
  `evidence/gate-verify-20261119T194038Z.txt` (+ `.sha256`).
- **Correction after inspection (2026-11-19).** The first evidence file printed its hash table as
  `System.Object[]` (PowerShell array stringification) and quoted a manifest digest `c9630697…`
  that does not reproduce; both are **withdrawn**. Superseded by
  `evidence/gate-verify-20261119T195437Z.txt`, which lists the file hashes and the exact manifest
  command. Canonical manifest: 120 files, lines `<sha256>  <relpath>`, globally sorted by relpath,
  joined with `\n` (no trailing newline), sha256 of that text. The docstring edit also dropped the
  UTF-8 BOM at the head of `tests/unit/test_migration_reversal.py`; it is **not** restored in the
  current worktree (bytes `22 22 22`) — this sentence is superseded by D-020.

## D-020 — F-1: SQLite durability returned to its default; BOM claim withdrawn (2026-11-20)

- **Finding F-1** (inspection `artifacts/phase3-independent-inspection-20261120.md` §5.2): `connect()`
  carried `PRAGMA synchronous = NORMAL`. It arrived in commit `7613f69`, which recorded D-017 for an
  *index* decision only; no entry covered the pragma, and AGENTS rule 10 requires one for a contract
  change. With WAL, NORMAL keeps the file consistent but can lose the **last committed transaction**
  on power/OS failure.
- **Decision: revert.** The pragma is removed; every connection now uses SQLite's default
  (`synchronous = FULL`, value 2). WAL is retained. Rationale: the migration ledger and published
  signals are durability contracts, and no throughput measurement or accepted loss window was ever
  approved.
- **Reintroduction rule.** A future NORMAL opt-in needs measured throughput evidence, a written loss
  window accepted by the owner, a decision id, and inspection of the change. Never silently.
- **Tests.** `tests/unit/test_sqlite_pragmas.py` asserts `synchronous == 2` on a fresh connection
  and on three further connections (regression fence).
- **BOM correction.** D-019 stated the UTF-8 BOM at `tests/unit/test_migration_reversal.py` "has been
  restored". It has not: the worktree file starts `22 22 22` (`"""`), the HEAD blob starts
  `EF BB BF`. The claim is withdrawn; bytes are reported as observed, not adjusted to fit the note.
- **W3 correction.** D-019 recorded W3 as "not fixed"; it was fixed on 2026-11-19
  (`evidence/phase3-w3-20261119T203654Z.txt`) and is verified as advisory only.
- **Not changed.** No dependency installed, no research test executed, no MT5 call, no commit.

## D-021 — Phase 3 scope decisions: research tests out of scope; correction record and inspection package prepared (2026-11-20)

- **Research modules (`tests/unit/test_stageB_leakage.py`, `test_research_features.py`): `out_of_scope`.**
  Source: `PHASE3_PLAN.md` §1 (in-scope list is indicator primitives, strategy contract, one
  reference strategy, signal persistence, replay determinism; the same section states "No orders, no
  account access, no ML frameworks") and §8 (non-goals: no profitability claim, no optimisation).
  Both modules test `scripts/research_edge.py`, which imports `pandas`, `numpy` and `sklearn`
  (HistGradientBoosting/LogisticRegression). They are research-harness files added by commits
  `c192c16`/`1d489dd`, not Phase 3 deliverables.
- **Effect.** Their status remains `NOT_RUN` and they are **not** acceptance requirements for Phase 3.
  `tests/conftest.py` `collect_ignore` is a collection-scope measure only and is not PASS evidence.
  Executing them needs a separate external venv with `pandas` + `scikit-learn` (owner-approved) or
  the D-019 relocation; neither is done here. Scope was not changed unilaterally: the plan already
  excluded them.
- **BOM correction record.** `evidence/phase3-bom-correction-20261119T212414Z.txt`
  (`99762d78…5388`) explicitly supersedes the false "BOM restored" statements in D-019 and in
  `evidence/gate-verify-20261119T195437Z.txt`. Originals are preserved unmodified.
- **Inspection package prepared** (not executed): `artifacts/phase3-inspection-package.md` at the
  workspace root, outside the project snapshot. It lists requirements, files, commands, expected
  evidence, snapshot identity and the independence prerequisite.
- **No production code change** in this pass; the only project edits are this entry and
  `PROJECT_STATE.md`.

## D-022 — Phase 3 accepted (S7 PASS by isolated inspector run); D-019 formally deferred; Phase 2 clock split out (2026-11-20)

- **Phase 3 ACCEPTED.** Basis: an inspector execution run entirely under the `GuardianInspector`
  token (standard local account, non-admin, member of `Users` only, explicit deny of every
  write-class right on the frozen snapshot, verified by the inspector's own access-mask probes;
  ACL inheritance check 146 objects / 0 problems) against revision
  `1d489dde + c4bb33565fbec4af549f8d7788c7bdf080f34f1ece5f6c39198075ade823ac83` (120 files;
  manifest reproduced independently by the inspector before/after and by the preparer on the live
  tree). Results: junit **302 tests / 0 failures / 0 errors** (exit 0), **46**
  `test_migration_reversal` cases, **2** `test_sqlite_pragmas` cases, `journal_mode=wal` +
  `synchronous=2` (FULL — the D-020 fence holds), in-memory syntax gate green, storage probes all
  green (`revert_migration` refuses with ledger `[1,2,3]`; W3 `main.` qualification; malformed
  TEMP homonym fails closed; missing provenance refuses). Evidence:
  `artifacts/inspector-run-20261120T124202/` (raw logs with hashes) and
  `artifacts/phase3-closure-20261120T1255Z.md` (verdict `PASS`, machine-readable RESULT_JSON).
- **Authorization.** Owner mission "FINAL PHASE 3 CLOSURE" (2026-11-20): create/configure
  `GuardianInspector`, fix the four recorded documentation defects, and run the closure. The four
  docfixes are recorded in `evidence/phase3-docfix-20261120T1045Z.txt` (`2eb2a3a0…9093` + sidecar):
  stale `db.py` hash in `PHASE3-FINAL-HANDOFF.md` (now `177c3330…5c20`; `eab4ad1a…1d31b` was the
  pre-revert file), worktree-count scopes made explicit, missing probe sidecar added, FileStream
  preamble corrected (the two overloads exist; CreateFileW retained deliberately). No prior
  evidence file was modified.
- **D-019 formally DEFERRED.** Relocating the two research test modules
  (`tests/unit/test_stageB_leakage.py`, `tests/unit/test_research_features.py`) is postponed by
  owner decision (2026-11-20). They remain `out_of_scope` / `NOT_RUN` (D-021), are not Phase 3
  acceptance criteria, and are excluded from collection. Revisit when the owner approves the
  relocation or an owner-approved external research venv.
- **Phase 2 clock item split out.** `DEGRADED: clock_unverified:no_fresh_ticks` is recorded as a
  separate ticket `PHASE2-CLOCK-RECHECK-1` (re-run the smoke between 23:00Z and 21:00Z); it is not
  a Phase 3 acceptance condition and was never treated as one.

## D-023 — Phase 4 risk sizing: authorised scope and PRE-REGISTERED acceptance criteria (2026-11-21)

- **Authorisation.** Owner mission "FINISH & PUBLISH" (2026-11-21) authorises "the entire Phase 4
  scope from the proposal" (`artifacts/phase4-proposal-minimal.md`). That scope is deliberately
  narrow and is fixed here **before** implementation.
- **In scope.** A pure `Decimal` position-size function: caller-supplied equity number, risk
  fraction, stop distance in points, value per point per lot, lot step, min/max clamps; fail closed
  on any inconsistent/non-finite input. Module: `src/guardian/domain/risk/sizing.py`; no new
  dependency (stdlib `decimal` only).
- **Out of scope (unchanged).** Account access (`A-04` not requested), order construction (`A-05`),
  `MetaTrader5`, portfolio/correlation limits, kill switches, Phase 5, the existing strategy/risk
  rules, migrations `0001`–`0003`.
- **PRE-REGISTERED acceptance criteria (frozen before code):**
  1. `position_size` never risks more than `equity × risk_fraction` (checked over a numeric grid);
  2. result is always a non-negative multiple of `lot_step` and never above `max_lot`;
  3. monotonic: non-decreasing in `risk_fraction`, non-increasing in stop distance;
  4. fail-closed: zero/negative/non-finite equity or stop, float inputs, `risk_fraction` outside
     `(0, 1)`, non-positive `lot_step`/`min_lot`, `max_lot < min_lot`, `min_lot` not a multiple of
     `lot_step`, and a size below one lot step all raise `RiskError`;
  5. no trading surface: the new module imports no `MetaTrader5` and contains no
     `order_send`/`order_check`/`account_info`/`positions_get` reference (AST/source scan test);
  6. full suite green and `compileall` clean;
  7. independent PASS on the snapshot — **required for acceptance**, cannot be self-issued.
- **Status at registration:** criteria frozen; implementation not yet written. Results are appended
  after the tests run; the criteria above are not edited afterwards.
- **Results (2026-11-21).** Implemented `src/guardian/domain/risk/sizing.py` (`RiskError`,
  `RiskSpec`, `position_size`) and `tests/unit/test_risk_sizing.py` (29 tests). Full suite:
  **331 passed**, exit 0; `compileall` exit 0. S1–S5 hold by test; S6 green. **S7 is not
  obtained** — no read-only inspector is currently available, so Phase 4 stays *implemented but
  unaccepted*. No migration `0001`–`0003` was touched; no MT5, account or order surface added.
- **Disclosed residual (recorded, accepted with the mission).** The verification harness scripts
  were prepared by sessions sharing the assistant identity with earlier implementer/reviewer
  sessions. Mitigations: harness files pinned by SHA-256; the W3 protection was mutation-proven
  the same day (breaking the line fails both the suite test and the probe); all raw outputs
  archived with hashes; the executed checks derive verbatim from the official documents; the
  inspector token could not modify anything it judged (six/six write-class probes DENIED).
- **Consequences.** Phase 4 (risk) remains NOT STARTED and requires explicit human authorization
  before planning (`HANDOFF/04_PROMPT_TEMPLATES.md` §4). No commit/push was performed; the
  accepted revision is pinned by the manifest hash above, not by a commit id. The
  `GuardianInspector` password is never stored; a future inspector run needs an administrator
  password reset first.
- **Not changed.** No dependency installed, no research test executed, no MT5 call, no commit,
  no evidence file rewritten.

## D-024 — Phase 4 ACCEPTED (S7 PASS by isolated inspector run on commit 15a210a) (2026-11-21)

- **Phase 4 ACCEPTED.** Basis: an inspector execution run entirely under the `GuardianInspector`
  token (standard local account, non-admin, member of `Users` only; every write-class right
  explicitly denied on the frozen snapshot — six/six access-mask probes DENIED by the inspector
  itself; ACL inheritance check 247 objects / 0 problems) against commit
  `15a210a05c16744b9f114b13a86a76871b77b27c` ("guardian(phase4): Decimal risk sizing per
  pre-registered D-023"), snapshotted read-only via `git archive`; snapshot manifest
  `e939719fb6c3aed5fa98291cc844d9f50948116eb082702d92e0e8c0d8956ca1` (124 files) reproduced by the
  inspector before/after and independently by the preparer; `git diff 15a210a -- <Guardian
  subtree>` empty (worktree == commit).
- **All pre-registered D-023 criteria verified green** (independent PASS report
  `artifacts/phase4-inspection-20261121T1720Z.md`, raw evidence
  `artifacts/inspector-run-20261121T164943/` with hashes): S1 risk bound over 384 grid points plus
  the clamp-to-`max_lot` case; S2 lot_step multiple, range and cap; S3 monotonicity; S4 the full
  fail-closed matrix (21 cases, including `float`/`int` refusal per `PHASE4_PLAN.md` §2); S5 no
  trading surface (AST stdlib-only imports, no `MetaTrader5` import, no
  `order_send`/`order_check`/`account_info`/`positions_get` reference); S6 junit **331 / 0 / 0**
  (exit 0; 46 migration + 2 pragma + 29 risk cases), in-memory syntax gate green, durability fence
  `wal`/`synchronous=2` (D-020), storage probes green (migrations `0001`–`0003` untouched). Pinned
  hashes: `sizing.py fdebd07c…ea1f3`, `test_risk_sizing.py 0f335f5a…0153e53`, `db.py 177c3330…5c20`.
- **S7 obtained** — the gap honestly recorded in D-023 ("S7 is not obtained… implemented but
  unaccepted") is closed by this decision; the pre-registered criteria of D-023 were not edited.
- **D-019 unchanged: DEFERRED.** The research modules remain `out_of_scope` / `NOT_RUN` (D-021);
  this decision does not touch D-019's deferral.
- **R1 residual carried forward (disclosed).** The inspection harness was prepared by sessions
  sharing the assistant identity with earlier implementer/reviewer sessions. Mitigations: harness
  scripts pinned by SHA-256, criteria taken verbatim from `PHASE4_PLAN.md` §2/D-023, the executing
  token could not modify anything it judged, raw outputs archived with hashes, and the W3 shield
  remains mutation-proven. Two first-run scan false positives (a docstring mention of
  `MetaTrader5` and a relative intra-package import) were harness bugs, corrected and re-run;
  both runs' evidence is preserved (`b51fda69…e4f5`, `855f2cb2…5041`).
- **Consequences.** Phase 5 remains NOT STARTED and requires explicit human authorization. No
  commit/push was performed by the inspector; acceptance is pinned by the manifest hash and the
  commit id. `GuardianInspector` password is never stored; a future run needs an administrator
  password reset.
- **Not changed.** No source or migration edited by this decision; no dependency installed; no
  research test executed; no MT5 call; no evidence file rewritten.

## D-025 — D-024 registration published; PHASE2-CLOCK-RECHECK-1 attempt 1 blocked by a closed market (2026-11-21)

- **D-024 registration published** in this commit (`DECISIONS_LOG.md` + `PROJECT_STATE.md`),
  pinned to the independent PASS report `artifacts/phase4-inspection-20261121T1720Z.md`
  (`539a38e7…f51b`) and raw evidence `artifacts/inspector-run-20261121T164943/`
  (`inspector-evidence-v3…` = `855f2cb2…5041`). No source, migration or accepted evidence was
  touched; **D-019 remains DEFERRED, unchanged**.
- **PHASE2-CLOCK-RECHECK-1 — attempt 1 (2026-11-21T17:10Z).** Executed inside the nominal
  window (23:00Z–21:00Z) via `scripts/collect.py --bars M1 --count 5`. The DEMO terminal
  connected and returned 5 historical M1 bars (0 gaps), but the session is **Saturday — the
  market is closed**, so no fresh ticks exist and the broker clock offset cannot be measured.
  The run correctly reported `DEGRADED: clock_unverified:no_fresh_ticks`.
  **Verdict: BLOCKED — window unavailable; no PASS claimed or simulated.**
  Evidence: `evidence/phase2-clock-recheck-20261121T171004Z.txt` (`2b298b75…cb21` + sidecar).
- **Consequences.** The ticket stays OPEN; re-run between the Sunday open (23:00Z) and the next
  21:00Z halt. Full Guardian closure is **not** claimed while this ticket is open.
- **Not changed.** No code, migration or accepted evidence edited; no dependency installed;
  no MT5 order path touched (read-only DEMO collect); the only DB writes landed in

## D-026 — Monte Carlo risk engine: PRE-REGISTERED scope and acceptance criteria (2026-11-21)

- **Authorisation.** Owner mission "FINAL EXECUTION PROMPT" §2 (2026-11-21). Scope is fixed here
  **before** code.
- **In scope.** `guardian/domain/risk/montecarlo.py` + `scripts/montecarlo.py`: IID and moving-block
  bootstrap resampling, seeded reproducibility, drawdown distribution and threshold-exceedance
  probabilities, explicit configurable ruin definition with measured frequency, cost stress
  multipliers (1×/1.5×/2×/3×), dynamic equity-based sizing (risk fraction of *current* equity,
  `Decimal`), win-rate / risk-reward sensitivity, multi-strategy comparison, and a reproducible
  JSON+Markdown report (inputs, seed, data digest, assumptions, software revision, hashes).
- **Out of scope.** Market data fetching, MT5, orders, account access, parameter optimisation,
  new dependencies, Phase 5, changes to accepted Phases 1–4, migrations `0001`–`0003`.
- **PRE-REGISTERED acceptance criteria (frozen before code):**
  1. determinism: identical `(trades, seed, spec)` ⇒ identical result and identical report digest;
     a different seed changes the sample;
  2. IID and moving-block modes are distinct; `block_size >= n` reproduces the original sequence
     order (block contiguity proof);
  3. drawdown exceedance probabilities are monotone non-increasing in the threshold;
  4. ruin frequency is 0 for a strictly positive series at small risk and 1 for a guaranteed-loss
     series at high risk (the configured ruin definition is stated and measured);
  5. cost stress: increasing the multiplier never decreases mean max-drawdown or ruin frequency;
  6. sizing uses the *current* equity (equity compounds), all arithmetic `Decimal`, floats refused;
  7. fail-closed validation of every spec field (counts, ranges, finite values, block size);
  8. sensitivity grid returns one cell per (win-rate delta, RR multiplier) pair, deterministically;
  9. no trading surface: no `MetaTrader5`, no order/account calls (AST/source scan);
  10. full suite green, `compileall` clean, report includes data SHA-256 and software revision;
  11. independent PASS on the frozen snapshot (S11) — required for acceptance, never self-issued.
- **Status at registration:** criteria frozen; no Monte Carlo code exists in the repository
  (verified by search). Results appended after implementation; criteria are not edited afterwards.
- **Results (2026-11-21).** Implemented `src/guardian/domain/risk/montecarlo.py`,
  `scripts/montecarlo.py` and 30 tests in `tests/unit/test_montecarlo.py`; documented in
  `MONTE_CARLO.md`. Full suite: **361 passed**, exit 0; `compileall` exit 0. CLI smoke on a
  **synthetic demonstration input** (explicitly not market data): 2000 paths, seed 7, block 5,
  risk 1 %, ruin 50 %, cost ×1/1.5/2/3 → `content_sha256 = 01bc10455123f4bd0b5f7ebe54b8ed58…`;
  identical on a second run. Pinned hashes: `montecarlo.py = a901fca6…25c4`,
  `scripts/montecarlo.py = ed19b021…5be3`, `test_montecarlo.py = 8f7e2b14…a571`.
  **S11 not obtained** — no read-only inspector credential is available; the engine is
  implemented and tested, not accepted. One pre-existing test (`test_risk_sizing`
  allow-list) was corrected to admit the new stdlib imports; its `MetaTrader5` ban is intact.
  `data/guardian.sqlite3` (gitignored, never committed).

## D-027 — D-026 Monte Carlo risk engine ACCEPTED (S11 independent PASS) (2026-11-21)

- **Decision.** D-026 is **ACCEPTED**. Its pre-registered acceptance criteria remain unchanged; criterion 11 is satisfied by the independent S11 PASS. This entry records the result and does not expand D-026 scope.
- **Inspected revision.** Developer commit `701a4ddbee1d410d6accbec483e0096670c1f443`; frozen read-only snapshot SHA-256 `0eadf45eb82b0b27a62657a03836da5344ccdd6d33561b981d00eeff67e12192` (128-file manifest; 225 raw files). The inspector reproduced the snapshot hash before and after inspection; snapshot unchanged.
- **Inspector.** `DESKTOP-2NLF7CP\\GuardianInspector`, standard account, `admin_in_token=False`, `users_in_token=True`; six of six write probes DENIED on the snapshot; ACL review: 253 objects, zero problems. Inspection ran under the Inspector token in a separate execution context. Verdict: **PASS**.
- **Evidence.** Mirrored S11 record: `docs/agent-log/2026-11-21-s11-inspection.md` and `ایجنت/agent-log/2026-11-21-s11-inspection.md` (published in commit `8a33cdd867d4073a9ee1b280759fc1153abdaa0b`). Primary evidence file SHA-256: `7735b6a565f50cf7284b229f6a7075348754906e58c99098417112244c5d8c28`. JUnit SHA-256: `91bb5ab6d256ea786f56c1c45e303a09823a0baa0118543c50110fdf8617986a`. Additional probe hashes and first-run false-positive disclosure are preserved in the mirrored Inspector record.
- **Verification.** Full suite: 361 tests, 0 failures, 0 errors; 30 Monte Carlo cases; D-023 regression 31/31; independent D-026 probes C1–C10 PASS; CLI reproducibility confirmed by two runs with identical `content_sha256`. Snapshot and manifest matched; no technical finding remained.
- **Disclosures.** Three first-run red results were Inspector-probe false positives, corrected before the complete rerun; both evidence runs were retained. The 129-versus-128 file count difference is the local gitignored `data/guardian.sqlite3`, absent from the committed archive. No Monte Carlo source or test changes were made during S11.
- **Consequences.** Project state row 4b is updated to **ACCEPTED**. D-019 remains **DEFERRED**. `PHASE2-CLOCK-RECHECK-1` remains **OPEN** and separate from D-026 acceptance. This decision does not authorize Phase 5, live trading, order execution, PR merge, or other scope expansion.
- **Publication.** S11 evidence record was published at commit `8a33cdd867d4073a9ee1b280759fc1153abdaa0b`. This D-027 registration is a documentation-only follow-up; no source, tests, migrations, or accepted phase implementation are changed.


## D-028 — Phase 5 Firewall scope and weighted acceptance (2026-11-21)

- **Authorization:** Owner explicitly approved preparation and execution of permitted Phase 5 work in this conversation. This decision freezes scope and weights only; it does not waive entry gates.
- **Plan:** `PHASE5_PLAN.md` is the controlling Phase 5 plan.
- **Frozen weights:** F1=10, F2=12, F3=12, F4=15, F5=15, F6=15, F7=13, F8=8 (total 100).
- **Measurement:** A gate earns its weight only after a genuinely independent read-only Inspector PASS on a frozen snapshot. In-progress, blocked, failed, and unverified work earns zero. Phase completion = accepted weighted points / 100.
- **Entry blockers:** D-008 remains ACCEPTED_PROVISIONAL until a hermetic, hash-verified, reproducible environment and full verification evidence are recorded. Redaction bypass remediation and nested AGENTS scope clarification are required before Phase 5 implementation begins.
- **Safety:** DEMO remains disabled; A-05 and A-04 remain absent. This decision authorizes no broker order request construction/submission, no LIVE mode, no account financial-field access, no PR merge, and no live execution.
- **Phase 6–11:** No criteria or weights are implied; each requires a separate pre-registered owner-approved plan.

## D-029 — Full completion path with deferred Live Verification (2026-11-22)

- **Owner direction:** continue the Guardian project through all engineering phases to final readiness; defer live-environment verification until after engineering completion.
- **Scope:** Phase 5 remains governed by D-028/PHASE5_PLAN.md. Phases 6–11 require separate pre-registered plans before implementation; this decision does not invent their acceptance criteria or weights.
- **Completion:** engineering completion requires approved criteria, evidence, and independent read-only Inspector PASS for each applicable phase. Developer self-approval never counts.
- **Live verification:** no live execution is required for engineering completion and no LIVE mode is authorized. After completion, the owner may perform a separately authorized real-environment validation and return the raw evidence for review.
- **Safety unchanged:** DEMO remains disabled pending A-05 + explicit owner authorization; A-04 remains absent; no order construction/submission is authorized by this decision; no destructive operations, force-push, history rewrite, or unrelated-project changes.
- **Current blocker:** D-008 remains the immediate Phase 5 entry gate and must be closed with real hermetic/provenance/hash evidence, not documentation alone.


## D-008 — Offline dependency closure addendum (2026-11-22)

The D-008 engineering package from commit `234e73ea2586e393deb401a289681cbd9bcf6165` is being carried onto the current integration branch without replacing later Phase 4/5/11 records. Its original independent inspection verdict applies only to its frozen source snapshot; this integration snapshot requires a fresh independent inspection. The recorded engineering evidence reports a hermetic Python 3.11.8 venv, eight pinned distributions with hashes, offline installation with an unreachable index, clean `pip check`, 361 tests passed, and clean `compileall`. Residual limitation: read-only attributes are not an ACL boundary; wheelhouse binaries remain external to Git. D-008 is not marked accepted on this integration snapshot until the independent Inspector verifies it.

## D-030 — Owner-authorized post-completion autonomous DEMO validation (2026-11-23)

- **Owner instruction:** the owner explicitly authorized Guardian to autonomously open, manage, modify and close its own positions on the owner's DEMO account for one bounded 4-hour-30-minute validation. No per-trade human approval is required after all prerequisites pass.
- **Approval record:** `approvals/A-09.json`, record SHA-256 `sha256:a9f8d36cf8cee605773377a25bf929afc0e67e95ba74ccf80257b5754e893919`; previous record hash `sha256:d7126270255acacc2badfc3836ba8106fc4efc0670e3882457a9286d6d6acdf9`. The hash chain is tamper evidence only, not a cryptographic human signature.
- **Execution timing:** this authorization applies only to the separate Phase 12 validation, after Phases 5–11 are accepted and Phase 11 receives an independent read-only Inspector PASS. It does not accelerate or waive any engineering phase.
- **Instrument/account scope:** DEMO only, approved Aron Markets DEMO server/company, exact symbol `XAUUSD.`; LIVE and CONTEST are prohibited. One test only, exactly 4 hours 30 minutes, no restart/extension without new authorization.
- **Trading controls:** orders and order lifecycle are permitted only through the future isolated firewall execution process. Stop-loss, take-profit, risk, exposure, spread, freshness, clock, audit and kill-switch checks remain mandatory. A signal is never itself an order authorization.
- **Account-data boundary:** A-04 remains NOT GRANTED. This decision does not authorize reading balance, equity, margin or profit. If the existing sizing model requires equity, Phase 12 remains BLOCKED until A-04 is separately granted or a separately accepted fixed-volume risk contract is implemented and inspected.
- **Risk parameter:** the existing `0.25` value must be validated for exact unit and calculation path before use; no interpretation, increase or override is permitted.
- **Supersession:** this decision supersedes D-029 only to the extent that D-029 deferred the post-completion DEMO validation to an owner-operated run. The validation may instead be operated autonomously by Guardian under A-09. D-029's engineering sequence, independent inspection rules and prohibition on LIVE trading remain unchanged.
- **Non-authorization:** no Phase 5–11 order activity, no LIVE mode, no per-trade risk escalation, no credentials in logs, and no execution before all entry gates pass.
- **Plan:** `PHASE12_DEMO_EXECUTION_PLAN.md` is the controlling protocol. Its status remains BLOCKED until every prerequisite is accepted.
- **A-05 relationship:** A-09 supersedes the A-05 requirement solely for the single post-completion Phase 12 test after Phase 11 independent PASS. A-05 remains NOT GRANTED; no order activity is authorized in Phases 5–11.

## D-008 final independent inspection addendum (2026-11-23)

- Exact inspected code snapshot: `integration/d008-offline-closure-20261122` / `cc106b557586e3e4cd867897c642ae7dc7d3fd16`.
- Independent Inspector verdict: **PASS**; external report SHA-256 `029d9e9546514b4c058786c950abb542ef117a1361ae8fbe4f5318714b17079c`.
- Inspector reproduced the 140-file snapshot manifest (`912dbd85…0626`) with zero differences; wheel closure 8/8, builder verification exit 0, hermetic offline install exit 0, `pip check` clean, suite **374/0/0**, `compileall` exit 0.
- External evidence: primary `97d43f1b…1cec`; JUnit `7f6ccb45…d6c6`; builder `6af40108…e3f0`; offline install `1517a57a…529a`.
- Both mirrored logs are byte-identical; SHA-256 each `3ead974ca6109d9754e3c3fe3195f801fb60950036c475d0fc3534abdc2c474a`.
- D-1 remains pending local Windows ReadOnly verification (not ACL protection); D-2 remains an owner decision (no ACL change/risk acceptance); D-3 is verified mismatched, UNUSED and preserved (external SHA `404f36ed4512d1ac97c4b5d4a64f3bff152b07a3e3754224e734c28670126b8c`, committed lock SHA `ed42dbdc2c65bb1393c1313e9ffdc897badb615d41e41e337ab8109db1b81970`); D-4 omission is disclosed and Inspector evidence supplies final results.
- Status: **ACCEPTED_CLOSURE_PENDING_OWNER_DECISION**, not CLOSED. Phase 5 entry remains blocked until the outstanding administrative and formal Phase 5 entry gates are evidenced.
