# AUDIT — Phase 2, finding A2 (tick window / `copy_ticks_from` clock)

Second-pass, independent, read-only audit. No file was modified except this report.
No shell, no SQLite query, no live MT5 call: every statement below is derived from
repository text or is labelled as inference.

**Artifacts read**
- `src/guardian/adapters/mt5_market.py` (`ticks()` 190-215, `estimate_server_offset()` 128-155, `to_utc` callsite 199)
- `src/guardian/domain/market/broker_clock.py` (`offset_for`, `to_utc`, `eu_dst_bounds`)
- `src/guardian/application/market_data_service.py` (`collect_ticks` 218-278, clock guard 79-105)
- `scripts/collect.py` (tick branch, 97-100)
- `tests/unit/test_market_adapter.py` 104-120
- `evidence/ticks-20261105T104123Z.txt`, `evidence/collect-20261105T104123Z.txt`,
  `evidence/baseline-20261105T103857Z.txt`, `evidence/pytest-20261105T104123Z.txt`,
  `evidence/health-20261104T222834Z.json`, `evidence/preflight-20261105T100859Z.json`
- `configs/config.toml`, `.git/HEAD`, `.git/refs/heads/master`

---

## 1. What clock reaches `copy_ticks_from`

Exact expressions:

```python
190  start_utc = start_utc.astimezone(timezone.utc)
191  offset = self._clock.offset_for(start_utc)
192  server_naive = (start_utc + timedelta(seconds=offset)).replace(tzinfo=None)
193  raw = mt5.copy_ticks_from(symbol, server_naive, int(limit), mt5.COPY_TICKS_ALL)
```

- Line 190 normalises the caller's value to an aware UTC instant.
- Line 191 asks the **modelled** broker clock (`BrokerClock`, winter 7 200 s / summer
  10 800 s) for that instant. On 2026-11-05 the EU-summer window ends 2026-10-25
  01:00Z, so the answer is **7 200**.
- Line 192 adds it and **strips `tzinfo`**. The digits are therefore
  **server wall-clock** (13:19:00 for 11:19:00Z), not UTC digits.
- Line 193 hands that bare `datetime` to a compiled extension.

**Provable answer:** the argument is **server-naive** — a tz-less wall clock intended to
be server time. It is *not* UTC-naive (UTC would be 11:19, the code adds 2 h) and it is
*not* constructed as host-local.

**What is not provable from files:** the zone the binding actually applies. The installed
package is `MetaTrader5 5.0.6231`; `.venv/Lib/site-packages/MetaTrader5/` contains only
`__init__.py` (constants) and `_core.cp311-win_amd64.pyd`. The conversion is inside the
compiled module, so "wrapper reads host-local" is **not** verifiable here. It is also the
one point where a bare `datetime` is ambiguous: once `tzinfo` is stripped, Python's
`datetime.timestamp()`/`mktime` semantics are host-local by default, and the MT5 API
documents the parameter as server time. The code depends on which of those wins, and
never pins it.

**Second ambiguity, on the input side:** `astimezone()` on a *naive* `start_utc` silently
assumes host-local. `collect_ticks` rejects naive windows (`start_utc.tzinfo is None →
ValueError`, service:220-221) and `collect.py:98-99` passes an aware UTC window, so the
sanctioned path is safe there. A direct adapter call or REPL probe is not.

---

## 2. Does the code explain −12 600 s?

Observed: asked 11:19:00Z, ticks span 07:49:00–08:12:15Z. Offset = 07:49:00 − 11:19:00 =
**−12 600 s = −3 h 30 m**.

The modelled server offset is +7 200 s. **7 200 ≠ 12 600**, so the model cannot produce
this on its own; the extra term is 12 600 − 7 200 = 5 400 s, and the only natural 3.5 h
quantity in this stack is a host zone of UTC+3:30.

Trace with the shipped expression, assuming the binding resolves naive datetimes
host-locally (host = UTC+3:30):

| step | value |
|---|---|
| requested start (aware UTC) | 11:19:00Z |
| + modelled offset (line 192) | 13:19:00 server digits |
| binding resolves 13:19:00 as UTC+3:30 local | absolute 09:49:00Z |
| terminal reads 09:49 digits as *server* time | true UTC = 09:49 − 2 h = **07:49:00Z** |
| delta vs request | **−12 600 s** (exact) |

So yes: with a host-local binding, the shipped expression reproduces the observed start
to the second. Net shift = host offset (12 600 s) regardless of the +7 200 s term, which
cancels against `to_utc`'s own subtraction.

Alternative trace, no binding assumption: a **naive** `11:19` passed to `ticks()`.
`astimezone(utc)` reads it as UTC+3:30 → aware `07:49:00Z`; line 192 then gives 09:49
digits and the terminal starts at 09:49 server = 07:49Z. Same −12 600 s, same start.

Both traces fit the number. They differ in one observable way, which is the point of §3.

The 23 m 15 s width of the returned span is **not** derivable from the repo: it depends on
the probe's `limit` and the tick rate at 07:49–08:12Z, neither of which is recorded. Treat
the end time as unexplained.

---

## 3. Does the filter discard the result, and can it return non-empty?

```python
199  tick_utc = self._clock.to_utc(msc / 1000.0)
200  if tick_utc < start_utc: continue
202  if end_utc is not None and tick_utc > end_utc.astimezone(timezone.utc): continue
```

The bound is a **lower bound on the true-UTC tick time**, compared against the *original*
`start_utc` (11:19Z), not the shifted request.

Therefore:

- **Under the binding-local trace**, ticks at 07:49–08:12Z are all `< 11:19Z` and are all
  discarded. `ticks()` returns `out == []` — an empty list, **not `None`**.
- **Under the naive-input trace**, `start_utc` *is* 07:49Z, the ticks pass, and the list is
  non-empty.

**Deduction:** the probe's non-empty 07:49–08:12Z span cannot have come from `ticks()` with
`start_utc = 11:19:00Z` on the shipped path. Either the probe fed a naive datetime (so the
filter's reference point moved with it) or the probe read `mt5.copy_ticks_from` directly.
The stated probe therefore does **not** by itself exercise the collector's window contract.
This is an inference from code + the quoted numbers, not an observation.

**Can the function still return non-empty for a short window? Yes**, and that is why the
defect is invisible:

`copy_ticks_from` returns *forward from* the (too early) start, up to `limit`. On the
sanctioned path with an aware 10-minute window, the request starts ~3.5 h early; the first
~3.5 h of ticks are killed by line 200, and the true 10 minutes survive at the tail — as
long as `tick_limit = 200 000` is not exhausted first.

Arithmetic for the stored run (`evidence/ticks-20261105T104123Z.txt`, `--ticks-minutes 10`,
window 10:31:23–10:41:23Z, inserted **7 840**, status **OK**):

- observed rate = 7 840 / 600 s ≈ **13.1 ticks/s** (quiet session; consistent with the
  quiet-rate estimate, not the ~100/s peak).
- early span before the true window ≈ 12 600 s × 13.1 ≈ **165 000 ticks**.
- worst case consumed ≈ 165 000 + 7 840 ≈ **173 000 < 200 000**.

So the cap was not reached, the true-window tail reached the filter, 7 840 rows were kept,
and the run reported OK. The 7 840 figure is explained by the 10:41:23Z collection run —
**not** by the 11:19Z probe, which has no evidence file.

**Latent failure, verifiable in source:** `truncated = len(raw) >= tick_limit`
(service:256) measures the **post-filter** list. When 3.5 h of early ticks consume the cap,
`out` is empty, `len(raw) == 0`, `truncated` is False, `crossed` is 0, and line 270 sets
`status = "OK"` with `inserted=0` and `reason=""`. At the peak rate (~100/s) the 3.5 h burn
is ≈1.26 M ticks, so this is the expected outcome at peak, and it is recorded as a clean
success. This is an inference about rate, but the code path (empty → OK, no truncation
flag) is directly readable.

---

## 4. Verdict

**A2: CONFIRMED.** The tick window is converted to a bare, zone-less wall clock whose
interpretation is left to the binding/host. The observed −12 600 s is exactly a UTC+3:30
host offset and cannot be produced by the modelled +7 200 s alone. The contract test
(`test_market_adapter.py:104-120`) only asserts the naive value the code itself builds — a
fake cannot falsify the compiled wrapper, so the suite's green run says nothing about this.

**Tick data positionally trustworthy today? Partly — no as a window guarantee.**

- Per-row timestamps: plausible. `time_utc` comes from `time_msc` via `to_utc`, independent
  of the request window, and line 200/202 bound every stored row inside `[start_utc,
  end_utc]`. Rows cannot leak outside the requested window.
- Window coverage: **not trustworthy.** Coverage is incidental to the cap, and an empty or
  cap-exhausted run reports OK/0 with no reason, so status cannot distinguish "collected
  the window" from "collected nothing".
- Absolute UTC correctness rests on the *modelled* offset: `set_server_offset()` only writes
  `_measured_offset_s` and is never read by `to_utc` (related A6). Today that is benign
  because the measured 7 200 000 ms equals the winter model; it would not be if they
  diverged.
- DST edges are resolved by `to_utc`'s two-pass heuristic, not by evidence; unverified.

---

## 5. The six supplied facts — verified vs not

| # | fact | status | basis |
|---|---|---|---|
| 1a | git root = project dir, branch master, HEAD 82ab8b5 | **verified** | `.git/HEAD` = `ref: refs/heads/master`; `.git/refs/heads/master` = `82ab8b56cd45…dfbe` |
| 1b | 61 dirty paths | **not verified** | needs `git status`; `baseline-20261105T103857Z.txt` records `dirty: 57` at 10:38:57Z (consistent with 4 more touched files later, but not proof) |
| 2 | evidence SHA-256 prefixes (4) | **not verified** | no hashing capability; the hashes present in the baseline file are of `src/` and `tests/` files, not the evidence files |
| 3a | suite exit 0, 169 tests | **verified as recorded** | `evidence/pytest-20261105T104123Z.txt`: `169 passed in 24.36s`; I did not run it |
| 3b | compileall exit 0 | **not verified** | no compileall output in baseline or pytest evidence |
| 4 | time_sync HIGH 7 200 000 ms, MAD 0, 10 samples @10:41:54Z | **not verified** | needs SQL; no `time_sync` rows in any evidence JSON. Code (`record_time_sync`, offset*1000) makes 7 200 000 the expected value for a 7 200 s model — consistent, not confirmed |
| 5a | ticks 7 840 | **verified** | `evidence/ticks-20261105T104123Z.txt`: `inserted: 7840`, status OK |
| 5b | bars 9 843 | **not verified** | needs SQL; last health artifact (`health-20261104T222834Z.json`) shows 9 000, baseline shows 9 806 |
| 6 | probe 11:19:00Z → ticks 07:49:00–08:12:15Z | **not verified** | no evidence file; and its non-empty shape is inconsistent with `ticks()`'s own filter at an aware 11:19Z start (§3) |

Also noted, unverified: the host zone UTC+3:30 appears nowhere in `configs/config.toml`
(session `anchor_tz` is `America/New_York`, unrelated) or in any evidence file. It is
inferred from the 12 600 s figure. If the host is not UTC+3:30, the explanation in §2 needs
re-deriving.

---

## 6. What would settle the open points (not run — read-only, no shell)

1. `int(start_utc.timestamp())` as the argument, then re-probe: if the first tick lands at
   the requested UTC, the binding is host-local and the epoch form is the fix.
2. One probe through `MarketDataService.collect_ticks` with an aware window, printing
   `len(raw)`, `min/max time_utc`, and the value actually passed at line 193.
3. `SELECT status, inserted, reason, started_utc FROM feed_runs WHERE kind='ticks'` plus
   `SELECT MIN(time_utc), MAX(time_utc) FROM ticks` to confirm the 7 840 rows sit in
   10:31:23–10:41:23Z.
4. A unit test asserting the argument **type and epoch**, not the naive wall clock, and a
   test that cap exhaustion yields a non-OK status.

**Out of scope, noted only:** A6 (`set_server_offset` inert) and the "empty result = OK"
aggregation are independent defects; the second is what converts this window bug into
silent zero coverage and should be filed separately if not already tracked.
