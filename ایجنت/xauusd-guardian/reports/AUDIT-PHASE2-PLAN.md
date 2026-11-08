# AUDIT — PHASE 2 PLAN (pre-implementation)

Reviewer pass: 2026-11-04 (UTC). Target: `PHASE2_PLAN.md`, HEAD `82ab8b5`, working tree as found.
Read-only: no plan, code, config or test file was modified by this pass. One file created: this report.

Standard used: the eight Phase 2 concerns in the review brief (disconnect, invalid symbol, invalid price,
missing candles, duplicate data, stale ticks, timestamps, reconnection); `DECISIONS_LOG` D-001…D-010;
`AGENTS.md` hard rules; `tests/security/test_boundaries.py`; `PROJECT_STATE.md`. No master roadmap file
exists in the repository — see §5.

## 1. Conclusion

**PLAN VERDICT = CHANGES REQUIRED.**

The shape is right: read-only scope, no order path, layer placement consistent with the existing code,
approval-gated tasks, and a real attempt to bound tick storage. Four must-fix defects block implementation:

1. the history-availability table is a probe artifact and Q4 is built on it;
2. the R1/Q1 disk arithmetic is internally inconsistent and sized on a lower bound;
3. the test matrix leaves four committed failure modes uncovered;
4. gap/staleness semantics have no session model, so MD-04 cannot tell a weekend from an outage.

Two worth-considering items follow. None requires re-architecting; all are plan edits.

## 2. Must fix

### M1 — §2 table and §10 Q4: "bars available" is the request size, not the history

**Position:** `PHASE2_PLAN.md` §2 row "Bars available"; §10 Q4; §9 R6.

**Problem:** all four timeframes report exactly 5,000 bars. That is the count the probe asked for, not what
the terminal holds. Independent read-only probe today, same terminal and symbol, requesting 200,000:

```text
init True (1, 'Success')
maxbars 100000000
M1 count 200000  2026-04-15T03:41:00+00:00 -> 2026-11-04T21:57:00+00:00
H1 count  57062  2008-03-11T02:00:00+00:00 -> 2026-11-04T21:00:00+00:00
```

M1 therefore holds at least 200,000 bars (~7 months), not 5,000 (3.6 d). H1 returned fewer than requested
(57,062), so that is the full available series (~18.6 years), not ~10 months.

**Impact:** Q4 asks the human to choose a backfill depth on false numbers, and R6 gates "deeper history"
behind a range-download approval that is not needed — `copy_rates_from_pos` already serves it. As written,
Phase 2 would be scoped to 3.6 days of M1 and 10 months of H1, which is not enough to feed the later
backtest phase.

**Evidence:** probe output above; `terminal_info().maxbars = 100000000`.

**Fix direction:** re-measure every timeframe with a large count (or binary-search the first available bar),
record count and first/last UTC timestamp per timeframe, then rewrite Q4 and R6. No range approval is
required for data `copy_rates_from_pos` already returns.

### M2 — §9 R1 and §10 Q1: the storage plan does not close

**Position:** §9 R1; §10 Q1; §5 (`ticks`, `quota_ledger`).

**Problem:** the plan states 1.8 GB/day, 16.5 GB free, and then recommends a 5 GB quota with 7-day
retention. At 1.8 GB/day, 7 days is 12.6 GB (76% of free space) and 5 GB is 2.8 days; both cannot hold.
The 1.8 GB/day figure is also a floor: the probe "hit the request cap", so ≥111 ticks/s is a lower bound,
not a measured rate. 1.8 GB/day ÷ 9.6M ticks/day implies 187 B/tick — an assumption the plan never states.

**Impact:** the one irreversible failure mode in this phase is filling C:, the system drive shared with the
MT5 terminal and the venv. A 12.6 GB database on 16.5 GB free also leaves no room for WAL growth or an
eviction VACUUM, which needs roughly a second copy of the file. `.gitignore` covers only `data/*.sqlite3`,
so `-wal`/`-shm` files (potentially GB) would surface as untracked in an already-dirty tree.

**Evidence:** plan §2, §9/R1, §10/Q1; measured today C: 16.5 GB free, D: 123.9 GB; `.gitignore` line 6.

**Fix direction:** measure bytes/tick on a real sample and show the arithmetic; make exactly one limit
binding (GB quota or days of retention, derived from the measured rate); define breach behaviour — MD-18
says refuse, which silently truncates a 7-day window at day 2.8 — and choose refuse vs evict-oldest
explicitly; check the quota per chunk, not per run, so one large window cannot overshoot; set the default
data root from the answer to Q1 (ticks → D:, bars → C:); widen the ignore pattern to `data/*.sqlite3*`.

### M3 — §7: matrix gaps against the required Phase 2 concerns

**Position:** §7 MD-01…MD-20; §5 "dedupe on ticks".

**Problem:** all eight named concerns have at least one row, but four committed behaviours are untested:

- **MD-09** covers `NOT_FOUND` only. D-003 Stage B `METADATA_MISMATCH` (contract_size, tick_size, digits,
  trade_mode, path token) is never exercised at collection time — the case where the symbol still exists
  but is no longer the approved instrument.
- §5 promises tick dedupe; no row stores duplicate ticks. MD-16 is about the time-sync sample set, not
  persistence, and no dedupe key is defined.
- `copy_rates_from_pos` returning None, empty, or fewer bars than requested (API failure / short history)
  has no row; MD-04 only covers holes inside a returned series.
- No row covers a truncated tail: the feed stops, the last bar is hours old while the market is open. A dead
  feed produces no interior gap and passes MD-04.
- Crossed quote (bid > ask) is also absent; MD-05/MD-06 cover bar OHLC and non-positive/NaN prices only.

**Impact:** G2 can go green while the feed is dead, the tick table is duplicated, or the adapter has switched
instruments.

**Evidence:** matrix rows as written; `tests/unit/test_symbol_identity_v3.py` covers Stage B at unit level
only, not inside a collection run.

**Fix direction:** add rows — metadata drift mid-run (BLOCK, zero writes); duplicate-tick idempotency with an
explicit key (symbol, time_msc, bid, ask); None/empty/short rates with FAILED vs DEGRADED defined; tail
truncation/stale bar; bid > ask.

### M4 — §7 MD-04/MD-07 and §10: gap and staleness have no session model

**Position:** §7 MD-04, MD-07; §10 Q1–Q5; §5 `data_gaps`.

**Problem:** XAUUSD trades roughly 23 h/day, 5 days/week; M1/M5/M15 series contain a ~49 h weekend hole every
week. "Gap > threshold" cannot both ignore that hole and detect a 2-hour outage. With one fixed threshold the
rule either flags every Monday as DEGRADED or misses real gaps. The plan has no session calendar or
expected-bar-cadence concept, and no gap/stale threshold values: config defines only `max_spread_points = 30`.
MD-14/MD-15 give time-sync numbers (2 s MAD, 10 samples); MD-04 and MD-07 say "threshold" with no value.
Separately, "run marked DEGRADED" has no consumer rule — nothing says whether Phase 3+ may read DEGRADED data.

**Impact:** a quality gate that cries wolf every weekend will be ignored; one tuned to ignore weekends cannot
see a real outage. Either way the phase's promise — data later phases can trust — is not enforced.

**Evidence:** grep of `settings.py`/`config.toml` shows no session, gap or staleness keys; §7 wording as above.

**Fix direction:** add a per-timeframe session / expected-cadence model (known closures plus expected bars per
interval), put gap and stale thresholds in config, and make DEGRADED consumption a human decision — this
should be Q6, not left to implementation.

## 3. Worth considering

### W1 — §4 and MD-20: the account-data guard does not cover the new adapter

**Position:** `tests/security/test_boundaries.py:82-93`; plan §4, MD-20.

**Problem:** `test_adapters_never_touch_sensitive_account_fields` parses exactly one hardcoded path,
`adapters/mt5_readonly.py`. Phase 2 adds `adapters/mt5_market.py`, the first new MT5 importer since that test
was written, and it escapes the guard. MD-20 only repeats the order-call and import checks — those do scan
`src/` and `scripts/` and would cover the new file.

**Impact:** a later edit in `mt5_market` (e.g. reading `account_info().equity` for sizing in Phase 4) would
pass the suite, while the same line in `mt5_readonly` would fail. A-04 is not granted.

**Evidence:** test body hardcodes the path; no other account-field check exists in `tests/`.

**Fix direction:** parametrize the test over `adapters/*.py` (or assert on the attributes read from the
`account_info()` result) and keep MD-20 as the regression.

**Safety answer for this plan:** no order API is reachable from anything proposed. The order-call AST scan
covers all of `src/` and `scripts/`; the new modules need only `copy_rates_*`, `copy_ticks_*`, `symbol_info*`,
`terminal_info`, and the existing `account_identity` (identity fields only).

### W2 — §5: `INSERT OR REPLACE` erases broker revisions

**Position:** §5 ("INSERT OR REPLACE on bars"); §8 G4/G6.

**Problem:** brokers revise history. Replacing a bar silently means an evidence manifest emitted yesterday no
longer replays equal today, and there is no record that the value changed.

**Impact:** weakens the tamper-evidence model the project relies on; G4 "deterministic replay" cannot
distinguish a revised bar from a corrupted one.

**Evidence:** §5 statement; the proposed schema has no revision or history table.

**Fix direction:** keep first-seen values and record revisions (history table, or per-bar content hash plus a
change log) — or make bars append-only with a revision column.

## 4. Record only

- §4 says "no module outside `firewall_process/` may ever reference order APIs … enforced by existing AST
  tests". `test_no_forbidden_trade_calls_anywhere` has no `firewall_process` exemption, and that directory does
  not exist. The implemented rule is stricter than the sentence; no action for Phase 2.
- §5 gives new contracts `schema_version = 1` while `contracts.SCHEMA_VERSION = 2`. R10 already records the
  1-vs-2 lag; defaulting new contracts to the global constant avoids a third version in flight.
- `numpy 2.3.4` is genuinely required by `MetaTrader5` (`requires == ['numpy>=1.7']`) but is absent from
  `requirements.lock`; R7's "documented" exists only in the plan. Also unstated: whether the adapter converts
  numpy structured arrays to plain dataclasses before the domain layer sees them (D-004 / AGENTS rule 7).
- `test_engine_modules_do_not_import_adapters` is a literal `"guardian.adapters"` substring check; a
  `from guardian import adapters` would pass it. Pre-existing, not introduced by this plan.
- Q5 (W1–W3) is not a Phase 2 blocking decision; it can be answered at T7 without gating T1.
- §4 draws `contracts.market → domain.market.quality`; the repo's dependency direction is `domain → contracts`.
  Read as data flow it is fine; read as a dependency it is inverted.
- T2 composes the frozen `Mt5ReadOnlyAdapter`. If MD-11/MD-12 need a fake MT5, the plan does not say whether
  that file may gain an injection seam.

## 5. Review scope and not covered

### Claims checked

| Claim | Result |
|---|---|
| HEAD `82ab8b5`, 27 dirty paths (11 M + 16 ??) | Confirmed (28 now, including this plan file) |
| `pytest-20261104T192237Z.txt` 93 passed, exit 0 | File tail read: `93 passed in 3.45s`, `exit_code: 0`; suite not re-run |
| Approval chain A-01…A-06, A-04/A-05 not requested | Confirmed by directory and `approvals/README.md` |
| Terminal build 6230, `maxbars=100000000` | Confirmed live |
| Bars available per timeframe | **False** — see M1 |
| 200k ticks in 30 min (cap hit) | Not re-measured |
| C: 16.5 GB, D: 123.9 GB | Confirmed live |
| numpy 2.3.4 required by MetaTrader5 | Confirmed (`importlib.metadata.requires('MetaTrader5')`) |
| No market_data code (`market_data/`, `collect.py`) | Confirmed: grep and filesystem, no matches |
| No order APIs in `src/` + `scripts/` | Confirmed: grep, no matches |

### Coverage of the eight required concerns

| Concern | Rows | Verdict |
|---|---|---|
| disconnect | MD-11 | covered |
| invalid symbol | MD-09 | partial — mid-run `METADATA_MISMATCH` missing |
| invalid price | MD-05, MD-06 | partial — crossed quote (bid > ask) missing |
| missing candles | MD-04 | partial — source None/short and tail truncation missing |
| duplicate data | MD-02, MD-16 | partial — tick-storage dedupe missing |
| stale ticks | MD-07 | covered (threshold undefined) |
| timestamps | MD-13…MD-17 | covered |
| reconnection | MD-11, MD-12 | covered |

### Not covered

- No master roadmap document exists in the repo (only the `PROJECT_STATE.md` phase table). The eight concerns
  in the review brief were used as the requirement baseline for question 3.
- Approval-chain hashes were not recomputed this pass (the Phase 1 audits did); §12's claim is accepted as
  previously verified.
- No throughput, quota or sqlite write benchmark was run; the R1 analysis is arithmetic on the plan's own
  numbers plus the measured free space.
- The suite was not re-run (read-only evidence file used instead). No tick byte-size measurement was taken.
- Findings are plan-level only; no implementation exists to review.