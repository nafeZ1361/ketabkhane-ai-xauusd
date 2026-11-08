# AUDIT — PHASE 2 PLAN REVISION 3 (final recheck)

Reviewer pass: 2026-11-04 (UTC). Target: `PHASE2_PLAN.md` Revision 3, HEAD `82ab8b5`.
Read-only: no plan, code, config or test file was modified. One file created: this report.

Standard used: the seven rev-2 findings (`AUDIT-PHASE2-PLAN-R2.md`: N1, N2, M1-residual, W-A, W-C,
W-D, N3); the task's "no new contradiction" instruction; `AGENTS.md` hard rules; a live read-only MT5
probe of the same terminal/symbol. Closed items M2, M3, W1, W2 were not re-audited.

## 1. Conclusion

All seven rev-2 findings are closed as written. One new contradiction, introduced by the rev-3
session config, blocks authorization: §7.1 models only the weekend closure and fixes it in UTC. The
live feed has a daily 21:00–22:00Z break (12 M5 / 4 M15 / 60 M1 bars). With `gap_tolerance_bars = 1`,
MD-04 turns that break into a gap on every Mon–Thu, the run is `DEGRADED`, and Q6 makes `DEGRADED`
non-consumable. The winter Sunday open is also 23:00Z, not the configured 22:00Z.

**Verdict: CANNOT AUTHORIZE** until the session calendar is fixed (S1). No safety defect: scope,
order/account prohibitions and the adapter boundary are unchanged.

## 2. Status of the rev-2 findings

| Finding | Status | Section that closes it |
|---|---|---|
| N1 resolution cliff | **CLOSED** | §2.1 (resolution column, cliff, 2018 scope), §3 out-of-scope, §7 MD-27, §10 Q4 |
| N2 short-response rule | **CLOSED** | §5 `feed_runs` per (run, timeframe, symbol), §7 MD-23 oldest-bar rule, MD-28, MD-29 |
| M1-residual depth | **CLOSED** | §2.1 measured maxima; Q4 now 3M/645,179/217,751/57,063/16,756, no 200k |
| W-A thresholds | **CLOSED** | §7.1 `gap_tolerance_bars`, `stale_after_bars`, `session_close_utc`, `min_bars_per_day`; cited in MD-04/07/24 |
| W-C quota duration | **CLOSED** | Q1 (2GB = ~1.75d peak/~12d quiet), §7.1 `max_tick_window_h=6`, R1 |
| W-D revision key | **CLOSED** | §5 `UNIQUE (symbol, timeframe, time_utc, content_sha256)`; changed bar adds a revision |
| N3 numpy pin | **CLOSED** | §9 R7 (no action/no lock edit), Q7, T1 (no numpy), §11 (no packages) |

W-A's specific ask (thresholds and config keys) is closed; S1 is a new defect in the same §7.1 block,
not a re-opening of W-A. Residual notes: Q4's counts are full-series, not 2018+ (W-1); MD-23's
"requested end" is undefined for a scoped request (W-2); R7 says numpy is "recorded in D-008" but
D-008 has no numpy line yet (W-3).

## 3. Must fix — S1 (new, introduced by rev 3)

### S1 — §7.1 `session_close_utc` vs the measured feed: daily break and DST not modeled

**Position:** `PHASE2_PLAN.md` §7.1 lines 114–122 (`session_close_utc = "fri 21:00 - sun 22:00"`,
`gap_tolerance_bars = 1`), §7 MD-04 line 129, MD-07 line 132, MD-24 line 149, §10 Q6 line 186.

**Problem:** the only closure encoded is the weekend window, in fixed UTC. The feed has a second,
daily closure: 21:00–22:00 UTC, on every trading day. MD-04 defines a gap as "more than
`gap_tolerance_bars` inside a session"; 21:00–22:00Z is inside the Mon–Thu session. The break is 60
M1 bars, 12 M5 bars and 4 M15 bars — all above the tolerance of 1 — so every Mon–Thu M1/M5/M15 run
gets a `data_gaps` row and is `DEGRADED`. Q6 then makes it non-consumable. H1 has exactly one missing
bar (not > 1, so tolerated); H4 is unaffected because the break falls inside a 4-hour bar. The
weekend window is also US-summer-only: in US winter the Sunday open is 23:00Z, but the window ends
at 22:00Z, so the first live hour is marked closed (a run there sees a ~48h-old last bar and can fire
`STALE_FEED`).

**Evidence (live, read-only, 2026-11-04):** terminal build 6230, `XAUUSD.`, server clock
`tick.time − system UTC = +2:00:01`.
- M5 2026-10-20: 276 bars, 01:00–23:55 server, no interior gaps; server +3 ⇒ 22:00–20:55Z, missing
  21:00–22:00Z. M5 2026-10-26: 275 bars, 00:05–22:55 server; server +2 ⇒ 22:05–20:55Z, missing
  21:00–22:00Z.
- H1 2026-10-15: hours 1–23 server, missing 0; +3 ⇒ missing 21:00Z. H1 2026-10-26: hours 0–22
  server, missing 23; +2 ⇒ missing 21:00Z. The break is fixed at 21:00–22:00Z, not at a fixed
  server-local hour.
- Weekend: Friday 2026-10-23 last bar 23:50 server (+3) = 20:50Z; Friday 2026-10-30 last bar 22:50
  server (+2) = 20:50Z (US summer close 21:00Z). Monday 2026-10-26 first bar 00:05 server (+2) =
  Sunday 22:05Z; Monday 2026-11-02 first bar 01:05 server (+2) = Sunday 23:05Z (US winter open
  23:00Z).

**Impact:** under the plan as written, the default M1/M5/M15 backfill is permanently `DEGRADED` and
Q6 blocks Phase 3+ from using it; or T4/T7 suppress the daily break outside the plan, which hides a
real 21:00–22:00Z outage and defeats the quality gate. A winter Sunday run at 22:00Z can also fail
`STALE_FEED` before the market opens. This is a scope/acceptance contradiction, not a style issue.

**Fix direction:** define sessions in a DST-aware form — either (a) the broker's server schedule
(daily 00:00–01:00 server break, weekend Friday 24:00 → Monday 00:00 server) converted to UTC with
the existing offset estimator, or (b) a UTC calendar with the daily 21:00–22:00Z break and a
US-Eastern weekend rule (Friday 21:00Z / Sunday 22:00Z in US summer; Friday 22:00Z / Sunday 23:00Z in
US winter). Cite the chosen schedule in MD-04/07/24/26. Do not raise `gap_tolerance_bars` to cover
the break: a 60-bar M1 tolerance would mask a one-hour outage.

## 4. Worth considering

### W-1 — Q4's 2018+ label carries full-series counts
**Position:** Q4 line 184; §2.1 table lines 27–31.
**Problem:** Q4 says "Intraday 2018 → now only" but lists M5 645,179 / M15 217,751 / H1 57,063 /
H4 16,756 — the full series from 2008-03-11. Live 2018+ counts are M5 625,609 / M15 208,926 / H1
52,273 / H4 13,678 (pre-2018 19,574 / 8,826 / 4,790 / 3,078). The listed depths are 3%/4%/9%/22%
larger than the scoped feed.
**Impact:** a human approving Q4 approves a depth that cannot be collected under the 2018+ scope; an
implementer who requests 645k M5 bars gets the full series and must filter. Storage still closes
(~350 MB); this is a planning-number error, not a safety issue.
**Suggestion:** label the full-series counts "available incl. pre-2018" and give the 2018+ counts, or
replace the counts with "from 2018-01-01 to now".

### W-2 — MD-23's "requested end" and scoped history start
**Position:** MD-23 line 148; Q4 line 184; MD-28 line 153.
**Problem:** MD-23 makes a short response `COMPLETE` only when its oldest bar equals the "known history
start." For a 2018+ request, the oldest bar is 2018-01-02, not 2008-03-11, so a literal reading marks
a complete scoped response `DEGRADED`. "Ends before the requested end" is also undefined for
`copy_rates_from_pos` (no end) and for the forming current bar.
**Impact:** if T2 uses `copy_rates_from_pos` for the 2018+ backfill, N2's failure returns for every
M5/M15/H1/H4 scoped run.
**Suggestion:** define completeness at bar-open/range granularity: oldest bar equals the requested
range start (or the known history start if the request predates it); newest bar is the last expected
bar of the range or the last closed bar while open. Add a row for "request starts after history
start" (MD-28 is the opposite).

### W-3 — R7 says numpy is "recorded in D-008" but D-008 has no numpy line
**Position:** R7 line 172; `DECISIONS_LOG.md` D-008 lines 67–73.
**Problem:** the plan asserts the recording in the present tense; the decisions log lists only
`MetaTrader5==5.0.6231` and `pytest==9.2.0`.
**Impact:** a reader cannot tell whether the recording is done or deferred; N3's substance (no
install/no lock edit) is unaffected.
**Suggestion:** change to "to be recorded in T8" or add the numpy line to D-008 as part of T8.

## 5. Record only

- §2.1's "UTC" labels are the terminal's server time, not UTC: `tick.time − now = +2:00:01`; raw
  02:00 server is 00:00Z, and H4's raw first bar 2008-03-11 00:00 is 2008-03-10 22:00Z. Depth counts
  and the 2018 cliff are unaffected; relabel or convert before using the table for session times.
- §11 line 195 says "interday scope 2018+"; the rest of the plan says intraday. Typo.
- W-D's UNIQUE key suppresses a revert to a previously seen content hash (A→B→A); the current content
  is still reconstructible, but the revert is not timestamped. Low.
- MD-07 says "older than `stale_after_bars`"; the config comment says "2× cadence". State the
  multiplication explicitly in the matrix.
- C: free space 15.8 GB (R2) vs 16.5 GB in rev 2; the 2 GB quota and D: root still close.
- H1's daily break is exactly at `gap_tolerance_bars=1` (1 missing bar, not >1); M15/M5/M1 exceed it.

## 6. Review scope and not covered

**Checked:** the seven rev-2 findings against rev 3; §2.1/§3/§5/§7/§9/§10/§11; AGENTS.md rules 2, 3,
5, 7; D-008; `config.toml`; live MT5 probes for the daily break, weekend boundaries, server offset and
the 2018+/full-series counts. No implementation exists; no plan/code/config file was modified.

**Not covered:** pytest, preflight and approval hashes were not re-run (no code change; prior audits
cover them); tick bytes/rate were not re-measured (R2's 118.7 B/tick and 16/111 ticks/s are taken as
reported); M2/M3/W1/W2 were not re-audited; the session calendar is inferred from bar timestamps, not
from broker documentation; the plan's "~22:00Z" probe time was not reconciled with the current clock
(~20:20Z) — counts differ by minutes, not materially.
