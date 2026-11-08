# PHASE 2 PLAN — Market Data (read-only)

**Status:** PLANNED / NOT STARTED · **Revision 3** (2026-11-04) — addresses `AUDIT-PHASE2-PLAN.md` M1–M4/W1–W2 and `AUDIT-PHASE2-PLAN-R2.md` N1–N3, W-A/W-C/W-D.
Inputs: `PROJECT_STATE.md`, `DECISIONS_LOG.md`, `reports/AUDIT-PHASE1-F7F8.md`, both Phase 2 plan audits, live read-only MT5 probes.

---

## 1. Objective

A validated, reproducible, read-only market-data layer for `XAUUSD.` that later phases can trust — no order capability, no account-financial access.

## 2. Reconnaissance (evidence, 2026-11-04 ~22:00Z)

| Item | Observed | Method |
|---|---|---|
| Branch / HEAD | `master` @ `82ab8b5` | `git rev-parse`, `git log -1` |
| Working tree | **27 dirty paths** (11 M, 16 ??) | `git status --porcelain` |
| Accepted evidence | `preflight-20261104T192250Z.json` — 9 checks, exit 0, `checks_sha256` recomputed = stored · `pytest-20261104T192237Z.txt` — 93 passed, exit 0 | re-hash + parse |
| Approval chain | A-01→A-02→A-03→A-06: each `record_sha256` and `prev_sha256` recomputed OK | re-hash |
| Terminal | build **6230**, `maxbars=100 000 000`, connected | `terminal_info()` |
| Phase 2 code | none | filesystem |

### 2.1 History depth — measured, not requested

| TF | Bars returned | Oldest bar (UTC) | Intraday resolution from | Evidence |
|---|---|---|---|---|
| M1 | **≥3 000 000** (still request-capped) | 2018-05-10 | 2018 | 3 M request saturated |
| M5 | **645 179** (full) | 2008-03-11 | **2018** | full series |
| M15 | **217 751** (full) | 2008-03-11 | **2018** | full series |
| H1 | **57 063** (full) | 2008-03-11 | **2018** | full series |
| H4 | **16 756** (full) | 2008-03-11 | **2018** | full series |

**Resolution cliff (decisive for Q4):** before 2017 all four intraday timeframes hold **258–272 bars per year** — one bar per weekday at 02:00Z. That is daily data stored under an intraday label, not hourly trading. 2017 is partial; true intraday begins in **2018**.

Consequences adopted by this plan:
- Intraday backfill is scoped to **2018 → now**. Pre-2018 bars are neither imported nor relabelled in Phase 2.
- T4 gains a resolution floor: a series whose bars-per-trading-day is far below the timeframe's expected cadence is quarantined (`DAILY_RESOLUTION_DETECTED`), never silently stored (MD-27).

### 2.2 Tick cost — measured

50 000 live ticks written to a throwaway sqlite in `%TEMP%` (deleted after; no project file touched):

```text
rows=50000  db_bytes=5935104  bytes_per_tick=118.7  (four-column PK; production adds run_id ⇒ slightly higher)
rate: 16 ticks/s in a quiet 52-min window; a 200k cap was hit earlier ⇒ ≥111 ticks/s at peak
```

| Scenario | Ticks/day | Storage/day |
|---|---|---|
| Quiet (16/s) | 1.38 M | **0.16 GB** |
| Peak (≥111/s) | 9.6 M | **1.14 GB** |

Bars: full M1+M5+M15+H1+H4 ≈ 4 M rows ≈ **350 MB**. Free space: **C: 15.8 GB** · **D: 123.9 GB**.

## 3. Scope

**In scope:** read-only MT5 data session; identity re-verification per run; incremental idempotent bars (2018+); tick capture for explicit windows under a hard quota; three-clock timestamp model with median/MAD offset estimator; validation (duplicates, ordering, session-aware gaps, staleness, crossed quotes, OHLC, zeros/NaN, resolution floor); persistence + migrations; data-health report; bounded reconnection; CLI; tests.

**Out of scope:** indicators, regimes, signals, sizing, risk firewall, order APIs, backtesting, daemons, GUI, AI/controller, pre-2018 intraday backfill, D1 relabelling.

**Prohibitions:** no `order_send`/`order_check`/`order_calc_*`, no balance/equity/margin/profit, no MT5/AutoClaw/Windows settings, **no package installation**, no commit.

## 4. Architecture

```text
scripts/collect.py · scripts/data_health.py
        ▼
guardian.application.market_data_service      (orchestration; no MT5 import)
        ▼
guardian.domain.market.quality                (pure rules over contracts.market shapes)
        ▼
guardian.adapters.mt5_market                  (ONLY MT5 importer; composes Mt5ReadOnlyAdapter)
        ▼
guardian.storage.market_store                 (sqlite; migration 0002)
```

Dependency direction stays `domain → contracts`; `contracts/market.py` holds shapes only.

Boundary rules (existing tests extended in T7): order APIs forbidden in `src/`+`scripts/` (AST); `MetaTrader5` only in `adapters/*`; **account-field guard parametrised over every `adapters/*.py`** (W1); adapter converts numpy arrays to frozen dataclasses before data leaves the adapter.

## 5. Contracts and storage

`contracts/market.py`: `MarketBar`, `MarketTick`, `TimeSyncResult`, `DataQualityReport`, `FeedRun` — all default to the module `SCHEMA_VERSION` (2).

Migration `0002_market_data.sql`:

| Table | Key / rule |
|---|---|
| `bars` | `PRIMARY KEY (symbol, timeframe, time_utc)`; append-only |
| `bar_revisions` | `UNIQUE (symbol, timeframe, time_utc, content_sha256)` + `seen_utc`; a changed bar adds a revision, never overwrites (W2/W-D) |
| `ticks` | `PRIMARY KEY (symbol, time_msc, bid, ask)`; `run_id` for window scoping |
| `feed_runs` | **one row per (run, timeframe, symbol)** — a sparse H1 cannot degrade an M1 run (N2) |
| `data_gaps`, `time_sync`, `quota_ledger` | per gap / sample set / chunk |

`.gitignore` widened to `data/*.sqlite3*` (WAL/SHM never appear as untracked).

## 6. Task plan

| # | Task | Depends | Est. |
|---|---|---|---|
| T1 | `contracts/market.py`, migration 0002, store skeleton, `.gitignore` fix, config keys (§7.1) | — | M |
| T2 | `adapters/mt5_market.py`: bars/ticks, identity gate, reconnect policy, injection seam (protocol) — `mt5_readonly.py` untouched | T1 | L |
| T3 | Time-sync estimator (10 samples, median, MAD > 2 s ⇒ LOW ⇒ BLOCK) | T1 | M |
| T4 | Validators incl. resolution floor + session-aware gap/stale rules | T1 | L |
| T5 | `market_data_service`: per-timeframe runs, idempotency, per-chunk quota, manifests | T2–T4 | L |
| T6 | CLIs: `collect.py` (estimates size, refuses before start), `data_health.py` | T5 | M |
| T7 | Tests: §7 matrix, parametrised adapter guard, live smoke behind `-m live` | T1–T6 | L |
| T8 | Truth files, evidence, independent audit | T7 | S |

## 7. Test matrix

### 7.1 Fixed thresholds (config, not implementation guesses)

```toml
[market_data]
gap_tolerance_bars = 1      # 2+ consecutive missing bars inside a session ⇒ gap
stale_after_bars   = 2      # last bar older than 2× cadence while open ⇒ STALE_FEED
tick_quota_gb      = 2
max_tick_window_h  = 6
min_bars_per_day   = 0.5    # resolution floor factor vs expected cadence

[market_data.session]
anchor_tz  = "America/New_York"   # DST rule computed in code (2007+ rule); no tzdata package
week_open  = "sun 18:00"          # exchange time
week_close = "fri 17:00"
daily_break = "17:00-18:00"       # Mon–Thu maintenance halt, exchange time
calibrate_from_history_days = 30  # measure real boundaries; drift > 15 min is reported, not auto-accepted
```

The calendar is **anchored to exchange time, not UTC**: the daily halt lands at 21:00–22:00Z in summer and
22:00–23:00Z in winter, and the Sunday open shifts the same way. A fixed UTC string would flag every weekday
run `DEGRADED` (60 M1 / 12 M5 / 4 M15 bars per day) and would mis-time the winter Sunday open. T4 calibrates
the boundaries against the terminal's own last 30 days and reports any drift instead of silently trusting the
config values. If the calendar cannot be resolved, the run is `BLOCKED`, never `OK`.

| ID | Case | Expected |
|---|---|---|
| MD-01 | Valid M1..H4 bars (2018+) | accepted, replay-equal |
| MD-02 | Duplicate bar | idempotent, no second row, no revision |
| MD-03 | Non-monotonic series | rejected with reason |
| MD-04 | Gap > `gap_tolerance_bars` inside a session | `data_gaps` row, that timeframe's run `DEGRADED` |
| MD-05 | `high < low`, `close` outside range | rejected, field named |
| MD-06 | Zero / negative / NaN price | rejected |
| MD-07 | Last bar older than `stale_after_bars` | `STALE_FEED`, `DEGRADED` |
| MD-08 | Spread > `max_spread_points` | flagged, not tradable |
| MD-09 | Symbol absent | `NOT_FOUND`, no substitution |
| MD-10 | Terminal absent / wrong path | `CONNECTION_FAILED`, zero partial writes |
| MD-11 | Disconnect mid-run | bounded retry, `FAILED`, no silent gap |
| MD-12 | Reconnect after 2 failures | resumes, run-id preserved |
| MD-13 | 10 clean offset samples | median offset, HIGH |
| MD-14 | MAD > 2 s | LOW ⇒ blocks trading decisions |
| MD-15 | < 10 valid samples | `UNKNOWN` ⇒ BLOCK |
| MD-16 | Duplicate/stale samples in offset set | excluded |
| MD-17 | Broker-time / DST boundary | UTC preserved |
| MD-18 | Quota breach mid-window | refuse at the offending **chunk**, evidence written |
| MD-19 | Storage failure mid-write | rollback |
| MD-20 | AST: no order APIs; MT5 confined to adapters; account fields absent in every `adapters/*.py` | pass |
| MD-21 | Symbol present but metadata drifts mid-run | `METADATA_MISMATCH`, BLOCK, zero writes |
| MD-22 | Duplicate tick vs stated key | ignored, count stable |
| MD-23 | `copy_rates_*` → None / empty / **ends before the requested end** | `FAILED` / `FAILED` / `DEGRADED`; a short response whose **oldest** bar equals the known history start is `COMPLETE` (N2) |
| MD-24 | Feed stops while market open (no interior hole) | `STALE_FEED`, blocks downstream |
| MD-25 | Crossed quote (bid > ask) | rejected, counted |
| MD-26 | Weekend/holiday closure vs 2-hour outage | closure tolerated; outage ⇒ `data_gaps` |
| **MD-27** | Pre-2018 sparse series (≈1 bar/weekday) | `DAILY_RESOLUTION_DETECTED`, quarantined, never stored as intraday |
| **MD-28** | Request older than history start | `COMPLETE` + note, not `DEGRADED` |
| **MD-29** | H1 run short vs M1 long in the same batch | independent run rows; M1 stays `OK` |
| **MD-30** | Daily maintenance halt (17:00–18:00 exchange) across 30 days | zero `data_gaps`, no `DEGRADED` |
| **MD-31** | DST transition weeks (Mar / Nov) | boundaries shift by 1 h, cadence still correct, no false gaps |
| **MD-32** | Calendar calibration drifts > 15 min from config | `CALENDAR_DRIFT`, run `DEGRADED`, never silently accepted |

A green suite never overrides a safety failure.

## 8. Acceptance gates

G1 scope · G2 matrix green · G3 live read-only smoke · G4 deterministic replay (revisions explain differences) · G5 manifests with hashes · G6 auditor recomputes hashes · G7 no order path, identity gate active, fail-closed on unknown · G8 approvals recorded + truth files updated.

## 9. Risk register

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Tick volume 118.7 B/tick; 0.16 GB/day quiet, ~1.14 GB/day peak | fills whichever drive holds ticks | **one binding limit: 2 GB quota**, checked per chunk, breach ⇒ **refuse** (not evict); bars-only by default; windows ≤6 h |
| R2 | Data root | provenance | Q2: ticks → D:, bars in-project |
| R3 | sqlite throughput under tick bursts | dropped data | batching, WAL, chunked commits |
| R4 | One IPC per process | contention later | single collector process |
| R5 | Three clocks + DST | mis-dated bars | UTC is the only stored time |
| R6 | History is shallower than it looks (resolution cliff) | backtests on fake depth | §2.1 floor rule + MD-27; intraday scoped 2018+ |
| R7 | numpy is a real `MetaTrader5` dependency, absent from `requirements.lock` | policy drift | **no action in Phase 2** (no install, no lockfile edit); recorded as an existing transitive dep in D-008. Adding it to the lock is a separate approval |
| R8 | `.venv` not hermetic (**D-008**) | reproducibility | must close before Phase 5 |
| R9 | Phase 1 residuals W1–W3 | untested entry point | T7 adds preflight-path coverage; W2/W3 stay documented |
| R10 | Evidence `schema_version` lag | audit confusion | fixed in T8 |

## 10. Human decisions required

| # | Question | Recommended default |
|---|---|---|
| Q1 | Tick persistence? | **bars only by default**; ticks only for windows ≤6 h; 2 GB quota = ~1.75 days at peak or ~12 days quiet; breach ⇒ refuse |
| Q2 | Tick data root | **D:** `D:\xauusd-guardian-data`; bars stay in-project |
| Q3 | Timeframes | M1, M5, M15, H1, H4 |
| Q4 | Backfill depth | **Intraday 2018 → now only**: M1 ≥3 M (capped, from 2018-05) · M5 645 179 · M15 217 751 · H1 57 063 · H4 16 756. Pre-2018 excluded (daily-resolution masquerade) |
| Q5 | W1–W3 residuals | defer to T7 |
| Q6 | May Phase 3+ consume `DEGRADED` runs? | **No** — only `OK`; `DEGRADED` is inspection-only |
| **Q7** | numpy in `requirements.lock` | leave out in Phase 2 (no install); decide with D-008 before Phase 5 |

## 11. Requested authorization

```text
APPROVED: PHASE 2 IMPLEMENTATION / BY: HUMAN / AT: <UTC> / SCOPE: PHASE 2 ONLY
```

Authorizes T1–T8, project-local files (+ Q2 data root), interday scope 2018+, no packages, no commit. Does **not** authorize order execution, `order_check`, balance/equity (A-04), DEMO execution (A-05), dependency installation, Git history changes, or Phase 3+.

## 12. Evidence behind this revision

- Depth and tick cost measured live 2026-11-04 ~22:00Z; audit re-probe confirms M1 ≥3 000 000 from 2018-05-10, M5 645 179, M15 217 751, and the 258–272 bars/year cliff before 2017.
- `checks_sha256` of the accepted preflight recomputed = stored; approval chain A-01…A-06 recomputed OK.
- All must-fix items from both audits are addressed in §2.1, §5, §7, §9, §10; the session calendar (§7.1) is exchange-time anchored with history calibration. No implementation exists yet.
