# Phase 2 — remaining findings remediation

Date: 2026-11-05 · Mode: controlled implementation · Authorization: A3, A4, A6, A7 (A2 added in-session by the human)
Baseline (this run): A2 = independent pass, A5 = independent pass, clock = independent pass.

## Verdicts

| Finding | State | One-line evidence |
|---|---|---|
| A1 — tick age semantics | **PASS** | signed age + `|age| ≤ 5`; live probe: `age = −2 s` accepted on 5/5 samples |
| A3 — misleading test names | **PASS** | `+30 s` tick now asserted as age `−30` and rejected by magnitude |
| A4 — frozen fake timestamps | **PASS** | stamps computed inside `symbol_info_tick`; the 1 s case fails under the old sign |
| A6 — unused offset setter | **PASS** | setter and measured-offset conversion path removed; DST model is the only conversion authority |
| A7 — governance evidence | **BLOCKED** | `approvals/A-07.json` exists but is not verifiable as a human authorization |
| Historical tick contamination | **OPEN — approval required** | 7 840 rows, `10:31:53.372Z → 10:41:53.282Z`; no out-of-window rows |
| A2 — tick window conversion | **PASS** (fixed after authorization) | request is `utc + offset`; first live tick 0 s from the window start |

## Changes

| File | SHA-256 |
|---|---|
| `src/guardian/adapters/mt5_market.py` | `694DCE5A21D2B24F5125871788BFBEA5C2B73A054F86B2B064D703AF5DEAC3F5` |
| `src/guardian/application/market_data_service.py` | `E6964B2C315923635A4A3018BF3A0A61B096E98522EB84A995F9BC5F5A6C7130` |
| `tests/unit/test_market_adapter.py` | `AD545DBC4813383BF6BA77D26353BF0B5352643A9FAC1A91B343128AD123913F` |
| `tests/unit/test_market_service.py` | `AC7D497646E12FD817FC8622542875E066521B0D525FD9DFD798CB5BA4F56CFF` |

`DECISIONS_LOG.md` gained D-013 (age + single clock authority) and D-014 (window epoch); `CHANGELOG.md` gained two bullets; `PROJECT_STATE.md` gained a remediation block.

### A1
`tick_age_seconds` = `(now + model) − tick.time`. Contract, now documented in the docstring:
positive = the tick is older than server-now; negative = it is stamped ahead of it; 0 = same second.
`is_fresh_tick` = `tick.time > 0 and |age| ≤ 5`. The estimator calls `is_fresh_tick` — one copy of the policy, no inline duplicate.
Tests: 0/1/2/5 s pass and 6/30 s fail in **both** directions; `tick.time ≤ 0` is never fresh.

### A3 / A4
- `test_future_tick_is_rejected` (which asserted `+30` as age `+30`) replaced by `test_tick_far_in_the_future_is_rejected` asserting `−30`.
- `test_tick_age_is_measured_against_server_local_now` replaced by `test_tick_age_sign_convention` + a symmetric boundary test.
- The fake produces its stamp per call (`SimpleNamespace(time=…)`), so no timestamp is frozen at construction.
- `test_offset_estimator_accepts_a_one_second_old_tick` uses an advancing fake; the sample is genuinely 1 s old at the call and only passes because the gate is two-sided.

### A6
Determination: **remove**, not connect. A measured offset is one constant; `BrokerClock` resolves the DST offset per timestamp, and a constant would mis-shift history across a switch by an hour — the exact defect D-011 was written to prevent.
Removed: `set_server_offset`, `measured_offset_s`, `_measured_offset_s`, the `server_offset_s` constructor override, `_offset_or_model`.
`to_utc` → `self._clock.to_utc`. The service still records the measurement (`time_sync`, HIGH, `offset_ms = 7 200 000`), now asserted from the DB instead of from a fake's attribute.

### A2 — fixed after a live probe
The brief declared A2 an independent pass. The live probe showed otherwise, so the developer stopped and asked for authorization; the human granted it in-session.

| Argument passed to `copy_ticks_from` | First tick returned | Error |
|---|---|---|
| `datetime.fromtimestamp(start − 7200)` — previous code | `12:51:04Z` | **−14 400 s (4 h)** |
| `start + 7200` (int) — new code | `16:51:42Z` | 0 s |
| `datetime.fromtimestamp(start + 7200)` | `16:51:42Z` | 0 s |

Fix: `request_s = int(start_utc.timestamp()) + self._clock.offset_for(start_utc)`. The old assertion (`− 7200`) is replaced by fixed literals (`1796126400` winter, `1785589200` summer), so the test fails against the old code instead of restating the formula. `test_tick_window_request_follows_the_dst_model` covers both seasons.

End-to-end live run through `adapter.ticks()`: argument `1793904778` = `int(start) + 7200`, 2 116 rows over 122 s, first tick `16:52:58Z` — 0 s from the requested start.

Previously the over-request was invisible: the UTC-side filter dropped the extra 4 h, so the 10:41Z run still inserted 7 840 in-window rows; at peak rates the 200 k cap would have been exhausted before the requested window and the run would have reported `inserted=0`.

## Verification

| Check | Result | Evidence |
|---|---|---|
| Targeted tests | adapter 20/20, service file green, exit 0 | run during the change |
| Full suite | **174 passed**, exit 0 | `evidence/remediation-final4-20261105T170215Z.txt` (sha256 `5DEBB30933B65F87B1A39FF43464926A3088C188451E82155B9F05B0599CB322`) |
| `compileall src scripts tests` | exit 0 | same file |
| Baseline before changes | suite green, exit 0 | `evidence/baseline-remediation-20261105T124924Z.txt` (sha256 `BD0B058BC27C7169514E6DF906F964C74493B03AC6B72D4BA69644D508EF4D2C`) |
| Live age probe | 5/5 samples accepted, `age = −2 s`, offset 7200, MAD 0 | `evidence/live-tick-age-20261105T152210Z.txt` (sha256 `BEDDB2045D05BB60151D20226AD01349B80815CB7FD2BCDC0C90A59F446DE33F`) |
| A2 window probes | old form −14 400 s, `+offset` form 0 s | `evidence/a2-window-probe-20261105T165215Z.txt` (sha256 `A0120AE3C834D4A1C294CFB5ADF36FDA2616A1DCB0F6E186BDA271762669E211`), `…probe2…` (sha256 `A8BD6DE98BAF21CCB1BEDE7360C918E012727D6CF9723BB023BDD404DF967652`) |
| A2 end-to-end | 2 116 ticks, first tick 0 s after the window start | `evidence/a2-fixed-endtoend-20261105T165458Z.txt` (sha256 `24DBE969DC7FE987864CFFDCB10F09904726BAA439E911533F95860DB9279AB7`) |

The live age probe is the decisive A1 evidence: every sample carried `age = −2 s` because the broker clock leads the model. The old `0..5` window rejected all of them, which is why runs degraded to `clock_unverified:no_fresh_ticks` whenever the market was even slightly quiet.

## A7 — BLOCKED

`approvals/A-07.json` exists, but:

- `granted_utc` 2026-11-05T13:07:58Z equals the file's own mtime (16:37:58 local, host +3:30): it was written **after** the 10:41Z tick run and **after** the 11:18Z audit that recorded no such record.
- The hash chain is intact (`prev_sha256` = A-06 `record_sha256`), but `approvals/README.md` states a chain is tamper evidence only and that an approval must never be inferred from an agent's own statement.
- `PHASE2_PLAN.md` §11 still holds the unfilled template `APPROVED: PHASE 2 IMPLEMENTATION / BY: HUMAN / AT: <UTC>`.
- Nothing in the repository ties the record to a human message; the `approver` string reuses the template's own wording.

Per the brief, a record is created only if the original authorization can be verified. It cannot, so nothing was written, nothing was edited, and the finding stays **BLOCKED**. The existing A-07 is flagged, not deleted: it is user data and its provenance is the human's call.

## Historical tick contamination — analysis only, no writes

| run_id | kind | rows | first tick (UTC) | last tick (UTC) | duplicates |
|---|---|---|---|---|---|
| `e01f4fe785344c39a7957c35692fc4cb` (10:41Z run) | ticks | **7 840** | `2026-11-05T10:31:53.372` | `2026-11-05T10:41:53.282` | 0 |
| `129437e25f904f29a5fa4877276600be` (11:49Z run) | ticks | 1 554 | `2026-11-05T11:47:23.520` | `2026-11-05T11:49:23.428` | 0 |

All 9 394 rows satisfy `time_utc − time_msc = −7200 s` exactly: the timestamps are internally consistent, with no per-row DST shift.

The brief's affected range (`10:31:53Z … ~11:44Z`) is **not reproducible**: no row exists between `10:41:53.282Z` and `11:47:23.520Z`, and the 11:49Z run lies outside the stated range. What the data does show is a *provenance* hazard: at capture time the request window was built with the pre-fix conversion (A2 above), so the 200 k tick cap could truncate the block before the intended window at peak rates. At the observed ~13 ticks/s it did not, and every stored row sits inside the intended window.

Quarantine plan (proposed, **not executed**):

1. Freeze: no deletes, no updates; run `e01f4fe7…` is the only candidate.
2. Re-collect `10:31:53Z → 10:41:53Z` after the A2 fix and compare row count, per-minute density (97 at the partial minute, then 770–804/min) and `(symbol, time_msc)` coverage against the stored run.
3. If coverage matches, mark the run verified-by-replay and keep it; if it does not, delete `WHERE run_id = 'e01f4fe7…'` **only after a separate human approval**, and record the deletion in `audit_events`.
4. The 11:49Z run is not a candidate: outside the stated range, and its window matches its data.

## Independent inspection

Reviewer: saved agent `审阅者` (read-only), run `065ea966`.

Round 1 — before the A2 fix:

> **Hashes:** 4/4 match the brief. **A1 PASS** … **A3 PASS** … **A4 PASS** … **A6 PASS** … **A7 BLOCKED** …
> **Regression guard FAIL** — the tick window conversion and its test encode the wrong value.
> **Suite:** `173 passed`, exit 0. **Must-fix:** the A2 conversion line and its test.

Round 2 — after the fix:

> **A2: PASS.** `mt5_market.py:210` passes `int(start_utc.timestamp()) + self._clock.offset_for(start_utc)`; … epoch+offset → delta 0, and the end-to-end run starts exactly at the window start (2 116 rows). Grep: no `datetime.fromtimestamp(start−offset)` left in `src`/`scripts`.
> **Tests:** both A2 tests assert fixed literals … the old code passed a datetime, so the int equality fails → genuinely regression-catching. Both seasons covered; the switch instant itself is not.
> **A1/A3/A4/A6:** no regression — adapter file 20/20 pass, service tests pass; all four hashes match.
> **Suite:** 174 passed, 0 failed, exit 0. **compileall** exit 0. **New must-fix:** none.

The developer did not self-approve: every verdict above is the inspector's, and the one must-fix it raised was fixed and re-inspected.

## STOP

Historical cleanup and Phase 3 wait for human approval. Nothing was committed or pushed; no database row was modified, inserted or deleted; no order API was called.

## Tick recollection & quarantine — BLOCKED (2026-11-05T17:15Z)

Authorized job: re-collect `10:31:53.372Z → 10:41:53.282Z` for run `e01f4fe7…`, compare, temporarily quarantine.
Result: **BLOCKED** — no collection was attempted and nothing was written. Verdict is not PASS.

Baseline (recon, read-only; independently recomputed by the inspector):

| Item | Value |
|---|---|
| `data/guardian.sqlite3` | sha256 `d45a088b039ec5b02bc7f66f31779aee323c8ca37729e96251f574d5b5cbbcb8`, 9 199 616 B, mtime 15:19:32 local (before this job) |
| Run `e01f4fe785344c39a7957c35692fc4cb` | 7 840 rows, `10:31:53.372Z → 10:41:53.282Z`, ordered-row digest `799bc8c72b5bb2c1a2bc58be2d874e979ea4b67fe1ecefe6c968d8cf61ed8f56`, status `OK` |
| Totals | 9 394 ticks, 12 feed runs, 0 quarantine rows |
| A2 | active: `mt5_market.py:211` = `int(start_utc.timestamp()) + clock.offset_for(start_utc)`; D-014 present |

Blockers, each confirmed independently:

1. **No absolute window in the collector.** `scripts/collect.py` exposes only `--ticks-minutes`, which always ends at `now()`. `MarketDataService.collect_ticks(start, end)` does accept absolute bounds, so this is a CLI gap, not an architectural one — but bypassing the reviewed entry point to hit the service directly would be an unreviewed path, and the brief says to stop instead.
2. **Same-database recollection cannot insert a row.** `ticks` has `PRIMARY KEY (symbol, time_msc, bid, ask)` and `_flush_ticks` uses `INSERT OR IGNORE`; run status only reflects crossed/truncated quotes. Re-collecting the identical window into the same DB would report `OK` with `inserted = 0` — a false success, not a comparison.
3. **No enforced quarantine.** `quarantined_series` is written by `MarketStore.quarantine` and read by nothing in `src/` or `scripts/` (only `tests/unit/test_market_store.py` reads it). `timeframe` is `NOT NULL`, while a tick run stores `NULL`. A row there would be a label with no isolation — the same inert-mechanism class as A6.

Not done, deliberately: no tick collection, no insert/update/delete, no quarantine row, no schema or code change, no second database, no commit or push. The only filesystem effect is `guardian.sqlite3-shm`'s mtime, touched by read-only SQLite connections; the main database bytes and hash are unchanged.

Minimum unblock (each needs its own approval):

1. `--ticks-start` / `--ticks-end` (ISO-8601 UTC) on `collect.py`, with the existing fail-closed guards.
2. A recollection target where PK collisions cannot be swallowed: a separate evidence DB via the existing `--db`, or a supersede path keyed by `run_id`.
3. A tick-scoped quarantine that a reader actually enforces (e.g. `feed_runs.status = 'QUARANTINED'` plus consumers filtering on it), with a documented reverse operation.

Then the job becomes: recollect into the evidence DB, compare digest/counts/per-minute density against the baseline above, mark the run quarantined, and leave the original 7 840 rows untouched. Deletion stays unauthorized.

Independent inspection: saved agent `审阅者`, run `c6fb2f27`, read-only, separate context, post-recon (not continuous — there is no live observer). Verdict verbatim: *“Baseline recomputed independently — all three match … A CONFIRMED … B CONFIRMED … C CONFIRMED … D CONFIRMED … E CONFIRMED … BLOCKED is supported. Minimum unblock: `--ticks-start/--ticks-end` in `collect.py` + a tick-scoped quarantine some reader actually enforces + a supersede path (PK collision blocks in-place repair); otherwise recollect into a separate DB via existing `--db`.”*

Phase 2 is not accepted, A7 stays BLOCKED, and Phase 3 is not started.

## Phase A/B — collection, recollection, quarantine (2026-11-05T17:38Z)

Result: **PASS** for the authorized workflow. Phase 2 acceptance remains **BLOCKED** on A7.

| File | SHA-256 |
|---|---|
| `src/guardian/storage/market_store.py` | `64C2D5820A22B3B675D22ADC5176B4B31138DD972A1D731084E21ABC958E3232` |
| `scripts/collect.py` | `40E3F08E0D0FBFD2CFFB98424C532036CCBBBA6AA22355764E74DD01FFD505BB` |
| `scripts/quarantine.py` | `13F7D5262D1FA9DF9C410F43E13193759B12EEBF3B668B2DBF1FAB8C0881830C` |
| `tests/unit/test_quarantine.py` | `F30D7FE4B1406AAC0713FF9C95B81ECB155B62BD3D911B723626D0F4021F6008` |
| `tests/unit/test_collect_cli.py` | `3D5B2FD8E6140143ADFB2BE5216EB524E19A4CCA8A8D7678DEAC9FD0FFD3C5AD` |

No migration was added; `ticks`, `feed_runs` and `quarantined_series` schemas are unchanged.

### A1 — absolute window
`--ticks-start` / `--ticks-end` accept only zone-carrying ISO-8601, must be given together, never combine with `--ticks-minutes`, never replace an explicit end with `now()`, and refuse reversed, empty or negative windows **before** opening a database. The relative form is byte-for-byte unchanged.

### A2 — non-colliding destination and no false success
Recollection writes to `data/evidence/recollect-20261105T172902Z.sqlite3` via the existing `--db`. A tick run with `inserted = 0` is reported `FAILED` with `inserted_zero:no_new_rows`; bars are untouched by that rule.

### A3 — functional quarantine
State is `feed_runs.status = 'QUARANTINED'`; the previous status is written to `audit_events`, so restoration is exact rather than a guess. `health()` and `last_bar()` exclude quarantined runs (`NOT IN (SELECT run_id … 'QUARANTINED')`, which keeps legacy rows with no run row visible). `scripts/quarantine.py apply|restore|status` is the operator surface. Tick runs have no timeframe, so the state intentionally lives on the run, not in `quarantined_series`.

### Recollection and comparison

| Item | Original | Recollected |
|---|---|---|
| run | `e01f4fe7…` (10:41Z) | `3087c765…` (17:29Z) |
| rows | 7 840 | 7 840 |
| first / last | `10:31:53.372Z` / `10:41:53.282Z` | identical |
| ordered digest | `799bc8c7…8f56` | `799bc8c7…8f56` |
| duplicates | 0 | 0 |
| missing / extra | — | **0 / 0** |
| field differences | — | **0** |
| per-minute density | 97, 804, 795, 770, 789, 799, 770, 762, 786, 775, 693 | identical |
| `time_utc − time_msc` | `−7200` on all rows | `−7200` on all rows |

Conclusion: the original run was **not** corrupted. The pre-A2 request shifted the window 4 h early, but the UTC-side filter kept only in-window ticks, and the tick cap was not reached at ~13 ticks/s. Replay proves it row for row.

### Quarantine cycle on the real database

| Step | visible ticks | quarantined runs |
|---|---|---|
| before | 9 394 | 0 |
| apply | 1 554 | 1 |
| restore | 9 394 | 0 |
| apply (final) | 1 554 | 1 |

The run keeps all 7 840 rows and its digest `799bc8c7…8f56` throughout; `audit_events` holds `QUARANTINE_APPLIED`, `QUARANTINE_LIFTED`, `QUARANTINE_APPLIED`. The database file hash moved from `d45a088b…cb8` to `cf1dac7c…a4b4` — metadata only (status + two audit rows); the row count and per-row digest are unchanged. `scripts/data_health.py` independently reports `ticks: 1554`, `quarantined_runs: 1`.

Restoration is one command: `python scripts/quarantine.py restore --run-id e01f4fe785344c39a7957c35692fc4cb`.

### Verification

| Check | Result | Evidence |
|---|---|---|
| Full suite | **198 passed**, exit 0 | `evidence/phaseA-final-20261105T173855Z.txt` (sha256 `8BFA0D8E60B3924B56D906463CE5E70C11B6FEB178854154CAED7DE11AFDDE22`) |
| `compileall` | exit 0 | same file |
| Recollection log | run `3087c765…`, 7 840 inserted, exit 0 | `evidence/recollect-20261105T172902Z.txt` (sha256 `C84EBF1911381DC0A2B9A32BFFD53DC8D79E62CAA18BA51ACBFBB270A94648D7`) |
| Comparison | digest equal, 0 differences | `evidence/compare-20261105T173033Z.json` (sha256 `9961A98363A9BED9C8847FC4C5239C5C68B7ED5F84C21032E62B494C5E3DEB60`) |
| Quarantine cycle | apply/restore/apply | `evidence/quarantine-cycle-20261105T173135Z.txt` (sha256 `76F5F7F8F5B960B7E60900D57B52712CA67AE73DC063175502626CFDD42569CF`) |
| Post-quarantine integrity | 7 840 rows, digest unchanged | `evidence/post-quarantine-20261105T173157Z.txt` (sha256 `C342466A5FCB31E0ED7B27C982072A709573B22894ACC462743A213EC550B6D2`) |
| Inspector | all PASS, no must-fix | run `5490120b`, post-execution |

### Phase C — A7 is mandatory
`PHASE2_PLAN.md` §8 gate **G8** requires “approvals recorded + truth files updated”. A7 is therefore an acceptance prerequisite, not an optional bookkeeping item. Its provenance is still unverifiable, so Phase 2 cannot be accepted by the agent, and the human decision is the only path.

### Phase D — remaining phases
Phases 3–11 are not started. The repository contains specifications for Phase 0/0.5/1/2 only; there is no Phase 3+ specification to implement, and inventing requirements is prohibited. They stay `NOT STARTED`.

**Overall verdict: `INCOMPLETE`** — the authorized tick workflow is PASS, Phase 2 is blocked on A7, later phases have no specification yet.
