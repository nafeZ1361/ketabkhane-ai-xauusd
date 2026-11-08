# AUDIT — Phase 2 implementation (read-only)

**Auditor:** independent reviewer (no authorship of this code)
**Tree audited:** `master` @ `82ab8b5`, working tree dirty (Phase 2 uncommitted)
**Date:** 2026-11-05
**Scope:** `contracts/market.py`, `domain/market/*`, `adapters/mt5_market.py`,
`application/market_data_service.py`, `storage/market_store.py`, `migrations/0002_market_data.sql`,
`scripts/collect.py`, `scripts/data_health.py`, `configs/config.toml`, the 8 new test modules,
and the three Phase 2 evidence files.
**Verdict: CHANGES REQUIRED** — two must-fix defects; the identity gate, broker clock, store and
quota path are sound.

---

## 1. Item results

| # | Item | Result | What I ran / read |
|---|---|---|---|
| 1 | No order capability | **PASS** | AST + token scan of `src/` and `scripts/` for `order_send`, `order_check`, `order_calc*`, `positions_*`, `orders_*`, `history_*`, `account_info`. Only `account_info()` in `mt5_readonly.py:138` (identity gate). Remaining token hits are a docstring (`mt5_market.py:7`), the identity-gate `account_info()` call, and `calibrate_from_history_days` key names — no trade API. `MetaTrader5` appears only in `adapters/mt5_market.py:55` and `adapters/mt5_readonly.py:34,59` (both `importlib`). No `balance`/`equity`/`margin`/`profit` reads anywhere. |
| 2 | Identity gate before any write | **PASS** | Four drifted identities pushed through `MarketDataService.collect_bars` on a fresh DB: `trade_mode=REAL`, wrong `server`, wrong `company` (trailing space), `contract_size=10`. All four returned `BLOCKED` with `bars=bar_revisions=feed_runs=time_sync=data_gaps=quarantined_series=0`. Gate order in `market_data_service.py:130-136` is guard → clock → first `record_run_start`. |
| 3 | Broker clock model | **PASS** | EU rule `eu_dst_bounds` = last Sun Mar / Oct 01:00Z; offsets +2/+3. Corroborated by the live series, not just unit tests: Mon–Thu M1 halt is 21:58Z→23:00Z on 2026-11-03 (= 16:58/18:00 ET, pins UTC+2); Fri 2026-10-30 H1 ends 20:00Z (=16:00 EDT) and Sun 2026-11-01 starts 23:00Z (=18:00 EST), a 51 h closure that only closes if both DST rules are right. Measured offsets 3600/10800/9000 s → `BLOCKED`, 0 bars; 7200 s → OK. A mismatch blocks, it does not shift. |
| 4 | Quota refuses, does not evict | **PASS** | 400 kB quota, 200 ticks pre-loaded, next 5 000 refused: `QuotaExceeded: quota 400000 B would be exceeded`. Rows before/after = 200/200. No `DELETE`/`VACUUM`/`DROP` token in `market_store.py`; `_check_quota` (`:65-70`) only raises. Service maps the exception to `BLOCKED` (`market_data_service.py:241-244`). |
| 5 | Full suite | **PASS** | `158 passed in 16.41s`, exit 0, wall 18.03 s — well inside the 5 min target. Matches `evidence/pytest-20261104T212634Z.txt` (158 passed, 28.47 s on the author's run). |
| 6 | Truthfulness of the live DEGRADED result | **FAIL** | The evidence JSON reports exactly what the code computed (`gaps:1`, `max_gap_bars:2`), so it is not falsified. But the M5 "2-bar hole" is not a hole: it is one missing bar at the Friday close plus one at the Sunday open, 49 h apart, merged by the gap counter. Adding only the Sunday-open bar makes the same series `gaps=0` (control below). H1 is a genuine 2-bar absence (2026-09-07 19:00/20:00Z) but the window ends exactly at the 18:00 ET reopen and 2026-09-07 is US Labor Day; with no holiday model the flag is conservative, not evidence of a feed hole. |

---

## 2. Must fix

### M1 — Tick collection requests the wrong window on any non-UTC host
**Location:** `src/guardian/adapters/mt5_market.py:154-158` (docstring at `:155`, `naive = ...` at `:157`,
`copy_ticks_from` at `:158`); no bound filter in `src/guardian/application/market_data_service.py:225-241`.

**Problem:** `copy_ticks_from` receives a naive datetime built from UTC
(`start_utc.astimezone(utc).replace(tzinfo=None)`). The MetaTrader5 wrapper converts a naive datetime
through local time, not UTC, so the request start moves by the host's UTC offset. The docstring at `:155`
("broker server time == UTC here") also contradicts the broker-clock model the same module implements.

**Evidence (live, read-only, 2026-11-04T21:42:27Z, host UTC+3:30):**
```
naive UTC        -> first tick 18:07:27Z  (delta vs requested start -12600.6 s)
int epoch        -> first tick 21:37:27Z  (delta -0.6 s)
naive server(+2h)-> first tick 20:07:27Z  (delta -5400.7 s)
```
A 5-minute window returned ticks starting 3.5 h earlier. With `tick_limit=200_000` the cap is consumed
before reaching the requested window at normal tick rates, so `collect.py --ticks-minutes 30` can store
200 000 ticks, report `inserted=200000 / status OK`, and contain none of the requested 30 minutes.
Per-tick `time_utc` conversion is correct; only the window is wrong, which is why nothing else caught it.

**Impact:** the tick capability advertised in the plan (`Q1`, `MD-18`, `MD-22`) silently produces a
series outside the stated window and reports success.

**Fix direction:** pass an epoch integer (`int(start_utc.timestamp())`) — proven correct in the probe —
or construct the naive value in local time; then filter the returned ticks to `[start_utc, end_utc)`
before `dedupe_ticks`. Add a test that asserts the argument handed to `copy_ticks_from` and one that a
tick outside the window is dropped.

### M2 — Gap counter merges missing bars across a session closure
**Location:** `src/guardian/domain/market/quality.py:145-164` — the loop skips closed boundaries
(`if calendar.is_open(...)` at `:146`) without closing the current run; `run` is only reset at `:153`
when an open bar is present.

**Problem:** `run` accumulates across the weekend. A missing bar at the Friday close and a missing bar at
the Sunday open become one "2 consecutive missing bars" event, although they are 49 h apart and in
different sessions. `MD-04` defines a gap as missing bars *inside a session*.

**Evidence:** `data/guardian.sqlite3` `data_gaps` rows 1 and 3: `gap_start_utc=2026-10-23T20:55Z` and
`2026-10-30T20:55Z`, `bars_missing=2`. The M5 series there is `…20:50Z` (Fri) → `22:05Z` (Sun), a
177 300 s jump. Isolated reproduction with the same shape:
```
Sun-open bar ABSENT  -> DEGRADED gaps=1 max=2
Sun-open bar PRESENT -> DEGRADED gaps=0 max=0   (Friday edge unchanged)
```
The Sunday 22:00Z bar is absent because the first tick lands at 18:05 ET; the Friday 16:55 bar is absent
because the last M5 bar is 16:50 ET. Each edge alone is tolerated; together they are reported as a hole.

**Impact:** every weekend with tight edges becomes `DEGRADED`; the current M5 live result is a false
alarm, and under `Q6` (`only OK is consumable`) a complete series is blocked from Phase 3 use by a
non-existent hole.

**Fix direction:** when `is_open` is false, flush the pending run (emit a gap only if
`run > gap_tolerance_bars`) and reset `run=0`, `run_start=None`. Keep the existing tolerance semantics
for contiguous open boundaries. Add a regression test with the Fri/Sun shape above.

---

## 3. Worth considering

### W1 — `time_sync` rows assert HIGH confidence that was never measured
**Location:** `src/guardian/application/market_data_service.py:94` —
`record_time_sync("HIGH", float(measured) * 1000.0, None, 10)`.
**Problem:** `domain.market.time_sync.estimate_offset` (the only code that computes MAD and can return
`LOW`/`UNKNOWN`) is never called by the service. `estimate_server_offset` returns a median rounded to
whole minutes with no dispersion, yet the store is written with `status=HIGH`, `mad_ms=NULL`,
`samples=10`. `data/guardian.sqlite3` `time_sync` rows 1–2 show exactly that.
**Impact:** `MD-14` ("MAD > 2 s ⇒ LOW ⇒ block") has a unit test but no production path; the evidence
table certifies a confidence it did not measure. Bars are still safe (conversion uses the model, and the
±90 s model check blocks gross drift), so this is an evidence-integrity defect, not a data defect.
**Fix:** have the adapter return `(offset, mad, n)` samples, run `estimate_offset`, persist the real
result and `BLOCK` when it is not `HIGH`; stop hard-coding `10`.

### W2 — The security tests certify less than the stated rule
**Location:** `tests/security/test_boundaries.py:14` (`FORBIDDEN_CALLS` = four `order_*` names) and
`:71-79` (sensitive-field check hard-coded to `mt5_readonly.py`).
**Problem:** the audit rule names `positions_*` / `orders_*` / `history_*`; none is in the denylist. The
plan (`W1`) says the account-field guard is "parametrised over every `adapters/*.py`", but the new
`adapters/mt5_market.py` is not parsed. State is clean today — my token scan found no such call — but the
test would not fail if one were added to `mt5_market.py`.
**Impact:** a future `positions_get` / `history_deals_get` / `account_info().balance` in the new adapter
passes CI.
**Fix:** match by prefix (`order_`, `positions_`, `orders_`, `history_`, `account_info`) and parametrise
the sensitive-field test over `adapters/*.py`.

---

## 4. Recorded only

- H1 `DEGRADED` at `2026-09-07T19:00Z` is a 2-bar absence in the broker series that ends exactly at the
  18:00 ET reopen; 2026-09-07 is US Labor Day. `session.py` has no holiday/half-day model, so `MD-26`
  ("holiday closure tolerated") is not implemented — the flag is conservative, but every backfill window
  containing a US holiday will stay `DEGRADED`.
- `adapters/mt5_market.py:46-50`: constructing with a `server_offset_s` more than 90 s from the model
  silently replaces the DST clock with a fixed offset — the exact failure mode the module docstring
  warns about. Unreachable from `collect.py` (which builds `Mt5MarketAdapter()`), so latent only.
- `PROJECT_STATE.md:12` still reads "CODE COMPLETE — GATE OPEN" and does not record the live
  M1 OK / M5+H1 DEGRADED result; `CHANGELOG.md` does not mention it either.
- `scripts/data_health.py:32-34` hard-codes the symbol `XAUUSD.` instead of deriving it from config or
  the DB.
- `data_gaps` accumulates one row per run, so the same hole is stored again on every re-collection
  (rows 1/3 and 2/3 here). By design as per-run evidence, but it is not deduplicated.
- `MD-21` ("metadata drifts mid-run") is checked only once, before the first fetch; nothing re-verifies
  between timeframes.

---

## 5. Coverage and not covered

**Executed:** full suite (`158 passed in 16.41s`); AST + token scan of `src/` and `scripts/`; four
identity-drift probes through the service on fresh temp DBs; four clock-offset probes (7200/10800/3600/
9000); quota-refusal probe; gap-detector reproduction and control; live read-only MT5 probes of
`copy_ticks_from` argument handling and of the measured server offset (21:41–21:42Z); SQL inspection of
`bars`, `data_gaps`, `time_sync`, `quarantined_series`.

**Not covered / not verifiable from here:** the tick path was never exercised end-to-end against the
real collector with persistence (would write to `data/`); the H1 Labor Day cause is an inference from the
bar shape (window ends at the 18:00 ET reopen) and the US holiday date, not from a broker holiday
schedule; the 2018+ backfill at scale and peak tick rates were not re-run; `MD-19` (storage failure
rollback) has no test; the 90 s clock tolerance's behaviour during the EU switch hour itself is untested
(the market is closed then, so the live series cannot distinguish it).