# AUDIT — PHASE 2 PLAN REVISION 2 (re-check)

Reviewer pass: 2026-11-04 (UTC). Target: `PHASE2_PLAN.md` Revision 2, HEAD `82ab8b5`, working tree as found.
Read-only: no plan, code, config or test file was modified. One file created: this report.

Standard used: the six findings from `reports/AUDIT-PHASE2-PLAN.md` (M1–M4, W1–W2); the four re-check questions in
the task brief (storage arithmetic, matrix coverage + session model, account-field guard, bar revisions);
`AGENTS.md` hard rules; `DECISIONS_LOG` D-003/D-004/D-006/D-008; `tests/security/test_boundaries.py`;
`configs/config.toml`. No master roadmap exists (unchanged from the first pass).

## 1. Conclusion

**PLAN VERDICT = CHANGES REQUIRED.**

Four of six findings are closed: M2 (storage arithmetic now closes), M3 (matrix gaps all covered), W1 (guard
generalised), W2 (revisions recorded). M1 and M4 are partially closed. The revision also introduces two internal
contradictions around the H1/H4 "full series":

1. **N1 (must fix)** — the H1/H4 history Q4 recommends is one bar per weekday before 2017, not hourly. Under the
   new session model it is either wrong-resolution data or a permanently `DEGRADED` run.
2. **N2 (must fix)** — MD-23 marks "fewer than requested" as `DEGRADED`, but H1/H4 always return fewer than a
   200 k request; with Q6 those timeframes can never be `OK`.
3. **M1 residual (must fix)** — Q4 still sizes M1/M5/M15 on the 200 k request; a live re-probe shows M1 alone
   serves at least 3 000 000 bars.

On the four questions in the brief:

| Question | Answer |
|---|---|
| Does the storage arithmetic close? | **Yes.** §9 R1 + §10 Q1/Q2 + MD-18: one binding 2 GB limit, per-chunk enforcement, breach ⇒ refuse, bars-only default, ticks on D:. 118.7 B/tick × 111/s ≈ 1.14 GB/day ⇒ 1.75 days at peak; 0.16 GB/day quiet. Safe on either drive. |
| Does the matrix cover the four gaps + session model? | **Yes.** MD-21 (metadata drift), MD-22 (duplicate tick), MD-23 (None/empty/short), MD-24 (stale tail), MD-25 (crossed quote), MD-26 (weekend vs outage). N2 is a defect inside MD-23, not a missing row. |
| Is the account-field guard generalised? | **Yes.** §4 bullet, MD-20, T7 parametrise it over every `adapters/*.py`; the current test hardcodes `mt5_readonly.py` at `tests/security/test_boundaries.py:71-83`. |
| Are bar revisions handled? | **Yes.** §5 append-only `bars` + `bar_revisions`, §8 G4. One minor key gap (W-D). |

The remaining defects are plan-text edits, not re-architecture. Storage, scope and the security boundary are
sound enough that only the history-depth claims block authorization.

### Per-finding status

| Finding | Status | Section that closes it / residual |
|---|---|---|
| M1 | **PARTIALLY CLOSED** | §2 table + §10 Q4 + §9 R6 rewritten, but Q4 depths are still the request size — see 'M1 residual' below |
| M2 | **CLOSED** | §9 R1, §10 Q1/Q2, §5 `.gitignore`, §7 MD-18 |
| M3 | **CLOSED** | §7 MD-21…MD-25 |
| M4 | **PARTIALLY CLOSED** | §7 MD-26 + §10 Q6 add the session model and the consumer rule; no gap/stale threshold values or config keys |
| W1 | **CLOSED** | §4 boundary bullet, §7 MD-20, T7 |
| W2 | **CLOSED** | §5 `bars` + `bar_revisions`, §8 G4 |

## 2. Must fix

### N1 — §2 / §10 Q4 vs §7 MD-26 / §10 Q6: "H1/H4 full to 2008" is daily-resolution before 2017

**Position:** `PHASE2_PLAN.md` §2 table lines 31–32 ("full series"), §10 Q4 line 165, §7 MD-26 line 135 and the
session paragraph line 137, §10 Q6 line 167.

**Problem:** The plan records H1 57 063 and H4 16 756 bars back to 2008 and calls them the full series, then
recommends "H1/H4 full to 2008" as backfill. Live per-year counts show that before 2017 the series is not hourly:

| Year | H1 | H4 | M5 | M15 |
|---|---|---|---|---|
| 2008 (from 03-11) | 215 | 215 | 215 | 215 |
| 2009 | 272 | 272 | 272 | 272 |
| 2010 | 260 | 260 | 260 | 260 |
| 2011–2015 | 258–259 | 258–259 | 258–259 | 258–259 |
| 2016 | 259 | 259 | 259 | 259 |
| 2017 | 2 491 | 779 | 17 275 | 6 527 |
| 2018 | 5 878 | 1 544 | 70 395 | 23 483 |
| 2019–2025 | ~5 900 | ~1 545 | ~70 500 | ~23 600 |

A 2013 H1 sample returns one bar per weekday at 02:00 UTC (`2013-01-02T02:00`, `01-03T02:00`, `01-04T02:00`,
`01-07T02:00`, …). That is daily resolution stored under an H1/H4 label, not 23 h of hourly bars. 2017 is
partial; full intraday starts in 2018. The same cliff exists in M5 and M15 (one bar per weekday through 2016).

**Impact:** Two mutually exclusive failure paths, both live under the plan as written:

- If the collector stores these bars as H1/H4, Phase 6 backtests on a series with roughly 1/23 of the bars it
  believes it has. G4 replay cannot reveal it: the bars are internally consistent, just not hourly.
- If MD-26's expected cadence (23 h/day) is applied, 2009–2016 produces ~22 missing bars per trading day —
  tens of thousands of `data_gaps` rows — the run is `DEGRADED`, and Q6 makes it non-consumable. If a run spans
  all five timeframes (MD-01 suggests it might), one sparse H1 tail marks the whole batch non-consumable.

Q4's recommendation therefore cannot be delivered as stated: it is either wrong data or data the plan's own gate
refuses. The M15 200 k floor (2018-05-21) happens to sit just after the cliff, which hides the problem for M15
but not for H1/H4.

**Evidence:** live read-only probe output above (counts per calendar year, first/last timestamps); plan lines
31–32, 135, 137, 165, 167. The pre-2017 counts are 258–272 per year for all four intraday timeframes, i.e. one
bar per trading day.

**Fix direction:** add a resolution column to §2 and a qualifier to Q4 — intraday (23 h) is available from 2018;
2008–2016 is daily-only, 2017 partial. Either restrict intraday backfill to 2018+, or store 2008–2016 as a
separate D1 series with its own timeframe label and make MD-26's cadence era-aware. Do not rely on the M15
200 k floor as evidence of usable depth.

### N2 — §7 MD-23 vs §2 H1/H4 and §10 Q6: full-history responses are always "short"

**Position:** §7 MD-23 line 132; §2 lines 31–32; §10 Q6 line 167.

**Problem:** MD-23 says `copy_rates_*` returning "fewer than requested" is `DEGRADED`. But
`copy_rates_from_pos` is a "most recent N" call: H1 returns 57 063 for a 200 000 request and H4 16 756 — the plan
itself calls these the full series. There is no way to request "all history" without over-requesting, so every
H1/H4 run satisfies the literal short condition and is marked `DEGRADED`. Q6 then makes it non-consumable.

**Impact:** H1 and H4 can never reach `OK`; G2/G3 can only pass by ignoring MD-23 or by special-casing the
implementation outside the matrix. If the run is per-batch, the `DEGRADED` H1/H4 result blocks M1/M5/M15 data
from the same run. This is independent of N1: even a clean post-2018 H1 series is "short" against a 200 k
request.

**Evidence:** MD-23 text; §2 counts (57 063 and 16 756 against a 200 000 request, labelled "full series");
Q6 text.

**Fix direction:** define completeness against the oldest available bar, not the request count: a response whose
oldest bar is the known history start is COMPLETE; a shortfall at the newest end or inside the requested range is
DEGRADED. Add one row for "request older than history start" and state run granularity (per timeframe vs batch).

### M1 residual — §10 Q4: backfill depth is still the request size, not the history

**Position:** §2 table lines 28–30, §10 Q4 line 165, §9 R6 line 152.

**Problem:** Rev 2 correctly labels M1/M5/M15 "request-capped" and says older bars may exist. But Q4 still
recommends "M1 ≥200 k (~7 mo) · M5 ≥200 k (~2.8 y) · M15 ≥200 k (~8.5 y)". A live read-only re-probe with
larger requests:

```text
M1  request 3 000 000 -> 3 000 000 returned, first 2018-05-10T09:28Z   (still request-capped)
M5  request 1 000 000 ->   645 179 returned, first 2008-03-11T02:00Z   (full series)
M15 request 1 000 000 ->   217 751 returned, first 2008-03-11T02:00Z   (full series)
M1  request 1 000 000 -> 1 000 000 returned, first 2024-01-09T18:40Z   (still request-capped)
```

At least 15× the Q4 M1 depth is served today; M5 is a 645 k series, not 200 k, and M15 a 218 k series.

**Impact:** an implementer following Q4 collects 7 months of M1 where ~8.5 years are served, and a third of M5 —
history Phase 6 loses for no reason, with no approval needed to get it. This is the original M1 defect at smaller
magnitude: the number still comes from the request, not the terminal. §9 R6's mitigation ("measured depths
recorded in §2") is therefore recording floors, not depths.

**Evidence:** probe output above; Q4 line 165; §2 "request-capped" notes; R6 line 152.

**Fix direction:** replace the three 200 k figures with the measured maxima or with a rule ("request max; stop at
the first short response"), and state M1 ≥3 000 000 (still capped, first bar 2018-05-10) / M5 645 179 / M15
217 751. Keep the caveat that M5/M15/H1/H4 pre-2018 is daily (N1).

## 3. Worth considering

### W-A — §7 MD-04/MD-07/MD-24: thresholds still have no values or config keys

**Position:** §7 lines 113, 116, 133; §7 session paragraph line 137; `configs/config.toml` (no gap/stale/session
keys; only `max_spread_points = 30`).

**Problem:** the session model is described qualitatively, but no numeric gap tolerance or stale threshold
exists. MD-07 says "beyond threshold", MD-24 says "stale tail", MD-04 says "gap inside a session" — none defines
the value, and no config key is named. Rev 1's fix direction asked for these in config.

**Impact:** T4/T7 must invent values; the matrix cannot state a deterministic expected result; a later tuning
change silently changes what `DEGRADED` means.

**Fix direction:** add per-timeframe `gap_tolerance_bars` (e.g. 1 missing bar tolerated, 2+ gap) and
`stale_after_s` (e.g. 2× cadence) to `config.toml` with defaults, and cite them in MD-04/07/24. This is the only
open part of M4.

### N3 — §9 R7 vs AGENTS.md rule 7 and §11: numpy pin inside "no packages"

**Position:** §9 R7 line 153; T1 line 96; §11 line 175; `AGENTS.md` rule 7; `requirements.lock`.

**Problem:** R7 says "add to `requirements.lock` as a transitive pin in T1". numpy is already installed (2.3.4,
pulled by MetaTrader5) but absent from the lockfile. AGENTS.md rule 7 bans numpy "without approval", and §11
authorises T1–T8 with "no packages" and does not name a numpy approval. T1 is thus asked to make a
dependency-declaration change that the authorization wording appears to exclude.

**Impact:** T1 either breaches AGENTS 7/§11 or leaves R7 unmitigated; an auditor cannot tell which was intended.
The pin is documentation, not an install, so this is not a blocker on its own.

**Fix direction:** either add an explicit "numpy transitive pin" line to §11/Q (human approval) or keep the pin
out of T1 and record numpy as an existing transitive dependency in the D-008 note.

### W-C — §10 Q1: the 2 GB quota's duration is not stated

**Position:** §10 Q1 line 162; §9 R1 line 147.

**Problem:** 2 GB is 1.75 days at the measured peak (1.14 GB/day) and 12.2 days at the quiet rate (0.16 GB/day).
Q1 asks the human to approve "2 GB" without saying how long that lasts or capping the window length, so a 7-day
tick window would refuse at day 1.75.

**Impact:** the human may approve a window the quota cannot complete. The behaviour is safe (refuse, no silent
loss) but surprising.

**Fix direction:** state the peak duration in Q1 and add a maximum window length (or let the CLI estimate and
refuse before starting).

### W-D — §5 `bar_revisions` has no key

**Position:** §5 line 87.

**Problem:** the table is `(symbol, timeframe, time_utc, seen_utc, ohlc, content_sha256)` with no primary key or
unique constraint. Seeing the same revised bar in two runs writes two identical revision rows.

**Impact:** duplicate revision rows; G4 replay still works but the revision count is inflated. Low.

**Fix direction:** `UNIQUE (symbol, timeframe, time_utc, content_sha256)` or a revision sequence per bar.

## 4. Record only

- C: free space at re-check was **15.8 GB**, not the 16.5 GB in §2 (same session; GiB/decimal and normal
  churn). The 2 GB quota still closes, and Q2 puts ticks on D: (123.9 GB), so no arithmetic change.
- R1 line 147 still frames the risk as "disk exhaustion on the system drive" and cites C:, while Q2 line 163
  defaults ticks to D:. Conditional on Q2 being declined; harmless, but the impact sentence is stale.
- 118.7 B/tick was measured on a four-column PK schema; production `ticks` adds `run_id` (and possibly an
  index), so the real bytes/tick is slightly higher. The 2 GB quota still binds; no re-run needed for the
  verdict.
- The 16 ticks/s sample was taken at 22:00Z (17:00 ET), the CME daily break — likely the quietest hour. Quota
  sizing uses the peak figure, so this changes the "0.16 GB/day" expectation, not the arithmetic.
- §2 line 46 "bars are cheap (200 k × ~90 B ≈ 18 MB per timeframe)" understates the available series: full
  M5+M15+H1+H4+M1 is ~4 M bars ≈ 350 MB. Still cheap.
- MD-20's account guard is still a lexical AST check of attribute names; `getattr(info, "equ" + "ity")` or
  `info._asdict()["equity"]` would pass. Pre-existing test limitation, not introduced by R2; W1's coverage gap
  is closed.
- `git status` shows 27 paths (11 M + 16 ??), matching §2 line 19; this report adds no path (`reports/` is
  already untracked).
- The plan's `SCHEMA_VERSION` (2) matches `src/guardian/contracts/schemas.py:17`; `configs/config.toml` keeps its
  own `schema_version = 1` for config, a separate namespace, not a contradiction.
- §4's dependency-direction sentence now reads `domain → contracts` and matches the existing code; the rev-1
  record-only note is resolved.

## 5. Review scope and not covered

### Claims checked

| Claim | Result |
|---|---|
| HEAD `82ab8b5`, 27 dirty paths | Confirmed (`git rev-parse`, `git status --porcelain`) |
| Terminal build 6230, `maxbars = 100 000 000` | Confirmed live |
| §2 M1/M5/M15 = 200 000, H1 = 57 063, H4 = 16 756 | Confirmed live; last bars drifted by minutes |
| §2 first bars per timeframe | Confirmed live (M1 2026-04-15 03:49 vs 03:45 in §2 — the 200 k window moved) |
| H1/H4 "full series" | Count confirmed; **resolution false before 2017** — N1 |
| M1/M5/M15 "request-capped" | Confirmed, and deeper than stated — M1 residual |
| 50 000 ticks → 5 935 104 B, 118.7 B/tick | Arithmetic confirmed (5 935 104 / 50 000 = 118.70); measurement not re-run |
| 16/s quiet, ≥111/s peak | Not re-measured; arithmetic 16→1.38 M→0.16 GB and 111→9.59 M→1.14 GB confirmed |
| C: 16.5 GB / D: 123.9 GB | D: confirmed; C: now 15.8 GB (see §4) |
| `SCHEMA_VERSION = 2` | Confirmed (`contracts/schemas.py:17`) |
| `.gitignore` only `data/*.sqlite3` | Confirmed (line 6); widening is T1 work |
| No gap/stale/session/threshold keys in config | Confirmed (`configs/config.toml`) |
| `adapters/` contains only `mt5_readonly.py` | Confirmed |
| Account-field test hardcodes `mt5_readonly.py` | Confirmed (`tests/security/test_boundaries.py:71-83`) |
| A-01…A-06 held, A-04/A-05 not requested | Confirmed |
| No order APIs in `src/` + `scripts/` | Confirmed by the earlier pass; not re-grepped this pass |

### Not covered

- Tick bytes/tick and tick rate were not independently re-measured (a 50 k tick capture at 16/s takes ~52 min).
  The 118.7 B figure is taken as reported; only its arithmetic is checked.
- The pytest suite was not re-run; the revision changes no code. The 93-passed evidence file was not re-parsed.
- Approval-chain hashes were not recomputed this pass (the Phase 1 audits did; A-02's scope was read for W-B).
- M1's true history start was not found: 3 000 000 bars is still request-capped. 2008-03-11 is the first bar for
  M5/M15/H1/H4, so M1 likely starts there too, but this is inferred, not measured.
- The pre-2017 resolution cliff is inferred from bar counts and timestamps; no broker documentation was available
  to confirm whether it is a server-history limit or a terminal setting. The inference is strong (258–272 bars
  per year, one per weekday at 02:00Z across four timeframes), but it is not a vendor statement.
- Findings are plan-level only; no Phase 2 implementation exists to review.