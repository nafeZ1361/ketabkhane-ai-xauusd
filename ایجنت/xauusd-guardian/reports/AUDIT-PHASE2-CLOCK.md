# AUDIT-PHASE2-CLOCK — post-fix verification of F-A / F-B / F-C

**Reviewer:** independent inspector. **Date:** 2026-11-05. **Tree:** `master` @ `82ab8b56cd4586ca63da429f427827052b62dfbe`, dirty.
**Scope:** `src/guardian/adapters/mt5_market.py`, `src/guardian/application/market_data_service.py`,
`tests/unit/test_market_adapter.py`, `tests/unit/test_market_service.py`, the four 10:41:23Z evidence files,
`data/guardian.sqlite3` (read-only), `approvals/`, `PHASE2_PLAN.md`.
**Verdict: BLOCKED** — two must-fix defects in the tick clock/window path, and six claims that could not be
executed in this session.

> This file replaces the pre-fix review previously stored at this path. Its P-1/P-2 must-fix items are quoted
> in §3.1/§3.4 because they are load-bearing for this verdict.

## 0. Method and hard limit

This session exposed **no shell/execution tool** — only read/list/grep/write. Therefore I could not run
`git status`, `pytest`, `compileall`, SHA-256, or SQLite queries. Everything below is either (a) verified by
reading files, or (b) explicitly labelled UNVERIFIED / inferred. I did not accept the developer's summary.
The prior audit reports in `reports/` are treated as prior-run evidence, not as this run's execution.

## 1. Repository state and the 56→61 delta

| Item | Result | Tier |
|---|---|---|
| Git root | `…\xauusd-guardian` (contains `.git/`) | verified (filesystem) |
| Branch | `master` (`.git/HEAD` → `refs/heads/master`) | verified (`.git/HEAD`) |
| HEAD | `82ab8b56cd4586ca63da429f427827052b62dfbe` | verified (`.git/logs/HEAD`, baseline line 1) |
| Commits | 2: `5ed9f73` initial Phase 1; `82ab8b5` "Track evidence artifacts…" | verified (`.git/logs/HEAD`) |
| Full `git status --porcelain` | **not obtainable** — no git executable/tool in this session | UNVERIFIED |
| Path count 61 | **not obtainable**; the only recorded count is `dirty: 57` at 10:38:57Z | UNVERIFIED |

**56→61 reconciliation (inference, arithmetically consistent, not enumerated).** The four code files existed
*and were hashed* at 10:38:57Z (`evidence/baseline-20261105T103857Z.txt` lines 2–5), so the delta contains
**no new source file** — the four were edited in place. Counting the observed artifacts:

```
56  before the pre-fix audit report
+1  reports/AUDIT-PHASE2-CLOCK.md (pre-fix review, now replaced by this file)
=57 exactly the "dirty: 57" recorded by the baseline run
+1  evidence/baseline-20261105T103857Z.txt      (written after its own status call)
+3  evidence/{pytest,collect,ticks}-20261105T104123Z.txt
=61
```

So the five new paths are the pre-fix audit report and the four evidence files; none is `src/` or `tests/`.
The stated starting figure **56 is not corroborated by any artifact** — the baseline says 57. If the pre-fix
report is older than the 56 snapshot, the 61 figure is off by one. Cannot resolve without `git status`.

## 2. The four files: what the current content actually does

A true `git diff` is impossible: the files are untracked and the baseline stored only digests, not content.
What follows is the current content at the lines that matter.

### 2.1 `src/guardian/adapters/mt5_market.py`

```python
30  def tick_age_seconds(tick_time_s: int, now_s: int, model_offset_s: int) -> int:
31      """Age of a **server-time** tick, measured against server-local now.
32
33      ``tick.time`` runs ahead of UTC by the model offset, so subtracting it from
34      raw UTC ``now`` yields a negative age and every sample would be rejected.
35      """
36      return int(tick_time_s) - (int(now_s) + int(model_offset_s))
39  MAX_TICK_AGE_S = 5
42  def is_fresh_tick(tick_time_s: int, now_s: int, model_offset_s: int, max_age_s: int = MAX_TICK_AGE_S) -> bool:
43      return 0 <= tick_age_seconds(tick_time_s, now_s, model_offset_s) <= max_age_s
```

Estimator (the only production user of the predicate):

```python
144                age = tick_age_seconds(int(tick.time), now, model)
145                if 0 <= age <= MAX_TICK_AGE_S:
146                    deltas.append(int(tick.time) - now)
150        median = statistics.median(deltas)
151        mad = statistics.median([abs(value - median) for value in deltas])
152        rounded = int(round(median / 60.0) * 60)
153        return rounded, int(mad), len(deltas)
```

Tick-window request (the "F1 fixed" claim):

```python
191        offset = self._clock.offset_for(start_utc)
192        server_naive = (start_utc + timedelta(seconds=offset)).replace(tzinfo=None)
193        raw = mt5.copy_ticks_from(symbol, server_naive, int(limit), mt5.COPY_TICKS_ALL)
199            tick_utc = self._clock.to_utc(msc / 1000.0)
```

### 2.2 `src/guardian/application/market_data_service.py`

```python
82  def _apply_clock(self, symbol: str) -> str | None:
89      self._clock_note = None
90      measured = self._adapter.estimate_server_offset(symbol)
91      if measured is None:
92          self._clock_note = "clock_unverified:no_fresh_ticks"
93          return None
...
103             self._store.record_time_sync("LOW", float(offset) * 1000.0, float(mad) * 1000.0, samples)
104             return f"server clock unstable (MAD {mad}s > 2s); refusing to timestamp bars"
105         self._adapter.set_server_offset(offset)
106         self._store.record_time_sync("HIGH", float(offset) * 1000.0, float(mad) * 1000.0, samples)
```

Bars (F-B propagation) and ticks (F-C block):

```python
178         if self._clock_note:
179             reasons.append(self._clock_note)
180             if status is QualityStatus.OK:
181                 status = QualityStatus.DEGRADED

237             clock_problem = self._apply_clock(symbol)
238             if clock_problem:
239                 return CollectionOutcome("BLOCKED", (), (clock_problem,))
240             if self._clock_note:
241                 # F-C: ticks are millisecond evidence — never stored on an unverified clock
242                 return CollectionOutcome("BLOCKED", (), (self._clock_note,))
243
244             run_id = uuid.uuid4().hex
245             run = FeedRun(run_id=run_id, symbol=symbol, kind="ticks", started_utc=now)
246             self._store.record_run_start(run)
...
265                 inserted = self._store.insert_ticks(run_id, clean)
```

### 2.3 The two test files

The new tests pin the implemented semantics rather than the intended ones:

```python
132     fake = FakeMt5(live_tick_time=int(_time.time()) + model_offset)
146     assert tick_age_seconds(now + model, now, model) == 0          # zero latency
147     assert tick_age_seconds(now + model + 1, now, model) == 1      # 1 s latency
154     assert is_fresh_tick(now + model, now, model) is True
155     assert is_fresh_tick(now + model + 1, now, model) is True
156     assert is_fresh_tick(now + model + 5, now, model) is True
157     assert is_fresh_tick(now + model + 6, now, model) is False
160 def test_future_tick_is_rejected():
163     # a tick timestamped ahead of server-local now has a negative age
164     assert tick_age_seconds(now + model + 30, now, model) == 30
165     assert is_fresh_tick(now + model + 30, now, model) is False
166     assert is_fresh_tick(now, now, model) is False  # age = -7200 (raw UTC vs server)
```

`test_market_service.py:229-238` adds the F-C test and asserts `store.health()["ticks"] == 0`; it does not
assert the absence of a `feed_runs` row.

## 3. Findings

### 3.1 F-A — must-fix: "age" is a lead, and the 0..5 window is one-sided (A1)

`tick_age_seconds` returns `tick_time − (now + model)`. That quantity is **not age**: it is the tick's
*lead* over modelled server-now. Age would be `(now + model) − tick_time`. Consequences of `0 <= lead <= 5`:

| Tick relative to modelled server-now | lead | Accepted? |
|---|---|---|
| exactly now | 0 | yes |
| 5 s in the future | +5 | yes |
| 6 s in the future | +6 | no |
| 1 s old | −1 | **no** |
| 5 s old | −5 | **no** |
| raw UTC (−7200) | −7200 | no |

So the gate accepts ticks **stamped up to 5 s in the future** and rejects **every tick even 1 s old**.
It passes today only because the broker clock leads the host UTC+model by ~1.5–1.7 s (prior live probe,
`reports/AUDIT-PHASE2-CLOCK.md` pre-fix §1), which lands ticks at +1/+2. In a quiet stretch where the latest
tick is >~1.6 s old, every sample is rejected, `estimate_server_offset` returns `None`, and the run becomes
`clock_unverified` — ticks BLOCKED, bars DEGRADED. That is F-A recurring in a quieter form, with the sign
reversed. If the broker clock is at or behind the model, the estimator is permanently dead.

This is exactly the prior P-1 must-fix, which was **not applied**:

> P-1 — `age = tick.time - (now + model)`, accept `0..5` … accepts only ticks stamped at or after modelled
> server-now … if the broker clock ran 1.6 s behind, the proposed test would reject every live tick … Fix
> direction: accept `abs(tick.time - (now + model)) <= 5`, keep `delta = tick.time - now` unchanged.

`abs(...) <= 5` keeps the same 5 s bound and the same `delta`; it only stops the direction from deciding the
outcome. It also correctly rejects a tick 30 s stale while accepting a normal 1–2 s old one.

**Fix:** `return abs(int(tick_time_s) - (int(now_s) + int(model_offset_s))) <= max_age_s`, or redefine
`tick_age = (now + model) − tick_time` and accept `-5..+5`. Add cases at −1, −5, −6, +5, +6 and a
negative-skew estimator test. **Severity HIGH.**

### 3.2 F-A — must-fix: the tick window is still shifted by the host offset (A2)

`ticks()` builds a **naive** datetime in server wall time and passes it to `copy_ticks_from`
(`mt5_market.py:191-193`). The installed wrapper converts a naive datetime through the **host's local
timezone**, not UTC and not server time. The project's own live probe recorded this on this host (UTC+3:30):

```
requested start 21:42:27Z
naive UTC          -> first tick 18:07:27Z   (delta ≈ −12600 s = host +3:30)
int epoch          -> first tick 21:37:27Z   (delta −0.6 s)   <- correct
naive server(+2h)  -> first tick 20:07:27Z   (delta ≈ −5400 s = +7200 − 12600)
```

The new code produces exactly the third line: `(start + 7200 s)` interpreted as local means the request
starts **5400 s early** on this host. The per-tick `to_utc` filter (`:199-203`) hides it in the stored rows,
so the 10-minute live run still looks right: at ~13 ticks/s the extra 1.5 h is ~70 k ticks, under the 200 k
cap, and the filter keeps only the requested 10 minutes → 7,840 rows. At peak (the plan measured ≥111
ticks/s) the 200 k cap is exhausted ~30 min into the buffer, the returned block ends **before** the
requested window, the filter drops everything, and the run reports `inserted=0` with
`tick_window_truncated:limit_reached` — DEGRADED, but no data. CHANGELOG:17 ("now shifted and filtered on
both sides") is therefore only half true: shifted, but still by the wrong field type.

The test at `test_market_adapter.py:104-120` asserts the naive server datetime is passed, which enshrines the
wrong contract; a fake cannot prove how the real wrapper interprets it.

**Fix:** pass `int(start_utc.timestamp())` (proven −0.6 s in the probe) and keep the UTC-side filter; assert
the epoch integer in the test. **Severity HIGH** (silent zero-coverage at peak; no corrupt timestamps).

### 3.3 F-A — estimator status (what does work)

Given a positive skew, the estimator does work: `age` +1/+2 passes, `deltas = tick.time − now = 7201/7202`,
median rounds to 7200, `mad` 0–1, `BrokerClock.matches(7200)` true, and `record_time_sync("HIGH", 7200000.0,
…)` runs at `market_data_service.py:106`. The 10:41:23Z tick run reports `status: OK`, which is reachable only
when `_clock_note is None`, i.e. only through that HIGH branch — so a HIGH row at ~10:41Z with
`offset_ms = 7 200 000` and `mad_ms ≤ 2 000` is **implied**. I could not query the table; this is inferred,
not observed.

### 3.4 F-A — test quality (A3, A4)

- `test_future_tick_is_rejected` is mislabelled: line 164 asserts a tick **30 s ahead** has age `+30`, and
  the comment above it says such a tick has a "negative age". Both cannot be true. The test does reject a
  far-future tick, but it never exercises the 1–5 s band in either direction, and it never tests a small
  negative age. The suite therefore certifies the inverted semantics.
- `test_offset_estimator_uses_the_modelled_server_clock` (line 132) freezes `live_tick_time` at construction
  with zero slack. If the wall clock crosses a second boundary before the first sample, `age = −1`, all three
  samples are rejected and the test fails intermittently. The prior P-2 must-fix asked for the fake to compute
  its tick time inside `symbol_info_tick`; that was not done. The 169-passed artifact is one sample, not proof.
  **Severity MEDIUM** for both.

### 3.5 F-B / F-C — PASS

`collect_ticks` calls `_apply_clock` at `:237`; a mismatch returns BLOCKED at `:239`, and a `None`
measurement (clock note) returns BLOCKED at `:240-242`. **Both precede** `record_run_start` (`:246`) and
`insert_ticks` (`:265`). The only production call to `insert_ticks` in the repo is `:265`
(`grep` over `src/` + `scripts/`); `scripts/collect.py` reaches ticks only through the service. So no run row
and no tick row can be written on an unverified clock. Bars propagate the note at `:178-181`, as the baseline
evidence shows (`clock_unverified:no_fresh_ticks`). F-B and F-C behave as claimed.

Two caveats, not blockers:
- A blocked tick attempt leaves **no DB trace at all** — no `feed_runs` row and no `time_sync` row (the
  `None` path returns before `record_time_sync`). The only record is stdout. Bars record a BLOCKED run; ticks
  do not. **A5, LOW.**
- The block is evaluated against the *current* quote, not the requested window. A historical window (yesterday)
  is refused at 02:00Z merely because no tick arrived in the last second. Defensible as fail-closed for live
  evidence; it makes quiet-hour backfill impossible. Note only.

### 3.6 Other code observations (A6)

`set_server_offset` (`mt5_market.py:115-117`) writes `_measured_offset_s`, but `server_offset_s`
(`:102-107`) returns `self._clock.offset_for(now)`, and neither `to_utc` nor `rates`/`ticks` ever reads
`_measured_offset_s`. The "pin" is a label: the deterministic model always wins. The service's
`test_clock_offset_is_pinned_before_collection` asserts a *fake's* attribute, so it cannot catch this.
**LOW**; either use the measured offset in conversion or delete the setter/property.

### 3.7 Governance (A7)

`approvals/` contains A-01, A-02, A-03, A-06 only; there is no structured Phase 2 record. `DECISIONS_LOG.md`
D-011 says "ACCEPTED AND IMPLEMENTED (2026-11-05, Phase 2 authorization)" in prose, and `approvals/README.md`
forbids inferring an approval from an agent's own statement. The brief states tick capture is authorized, so I
treat the *activity* as authorized; the missing A-07 record is a bookkeeping gap, **LOW**.

## 4. Live write: is 7,840 ticks + 37 bars in scope?

**Yes, by plan.** `PHASE2_PLAN.md` §3 lists "tick capture for explicit windows under a hard quota" in scope;
Q1 caps windows at 6 h and storage at 2 GB with refusal on breach. The run used `--ticks-minutes 10` (10 min,
7,840 rows) and `--bars M1,M5 --count 1000` (31 + 6 = 37 inserted), both inside those caps; `data/` is the
D-012 approved in-project root. No order API is called: `mt5_readonly.account_identity` (`:139-151`) returns
trade_mode/server/company/currency/leverage only, and the four files contain no `order_*`/`positions_*`/
`orders_*`/`history_*` call. The 37-bar figure is exactly the sum in `collect-20261105T104123Z.txt`
(31 M1 + 6 M5); the 7,840 is the tick run's `inserted`. **Scope: PASS.** Only the missing A-07 record (§3.7)
is a governance gap.

## 5. Test suite, compileall, hashes

| Check | Result | Tier |
|---|---|---|
| Full suite | `pytest-20261105T104123Z.txt` says `169 passed in 24.36s`, exit 0; command recorded as `--tb=short`, **not** `-q` | artifact only — UNVERIFIED |
| Prior suite | 161 passed at 22:08:20Z (71.12 s); 169 − 161 = +8 while the two changed test modules add 6 functions (15 + 15, prior audit counted 24) | inconsistency noted; parametrisation could explain it |
| `compileall` | no artifact exists anywhere in `evidence/`; not run | UNVERIFIED |
| Hashes | no hashing tool in this session; the four prefixes appear nowhere in the repo | UNVERIFIED |

Baseline (pre-fix) digests, from `evidence/baseline-20261105T103857Z.txt`, for the developer to compare:

```
mt5_market.py            C9F2BA9E05EE3B1EBF2D624C0AA024AC2CBF64C296E0986DAEDA7EABDC9E7B23
market_data_service.py   A1300B69D9BE4F7EF6037B729DF36542CD5226DD10798ABA0B32A9502F2236DB
test_market_adapter.py   EEC91418EF0293787C3C6230223C69F099D957B2469A55BFEACA7B16EC36DE09
test_market_service.py   6FE4D1C72D90C57A473C50F616735898AB55E9A865985E32DB92ED15948C4FA6
```

These are the *old* files: current content (e.g. `tick_age_seconds` present) necessarily differs. The
developer's current prefixes (052E604C1B2B5EFB, 568614E22704F8B1, AD72F70CFBF8DF79, 48FBE4ED1E42D803) are
16 hex chars, not full digests, and are not recorded in any manifest — I can neither confirm nor refute them.
The baseline file also begins with a UTF-8 BOM; byte-hash vs text-hash must be stated if this is ever rechecked.

## 6. H1: the 4 × 4-bar holes

**Confirmed as of 10:38:57Z, not re-queried.** The baseline run records
`run ('H1', 'DEGRADED', 0, 'gaps:4; max_gap_bars:4; clock_unverified:no_fresh_ticks')` — four holes of four
bars each in the 3,000-bar H1 window. The 10:41:23Z collect only ran M1/M5, so no post-fix H1 re-read exists.
I could not open the SQLite file (binary, no SQL tool).

**Data or model?** Not a clock artifact: a ±1 h DST error shifts a boundary by at most one bar, and the daily
halt is one bar — neither can create a 4-bar run. A 4-bar run requires four consecutive *open* hours with no
bar (`quality.py:146`). The two remaining explanations are (a) the broker genuinely has no bars during those
hours — US holiday or early close — i.e. **data**, and (b) the session calendar treats a 4-hour closure as
open — i.e. **model**. The calendar has no holiday/early-close rule (`session.py:7-8` models only the weekly
and daily halt), so (b) is plausible; the prior independent audit resolved the analogous H1 Labor-Day case as
a real 2-bar broker absence with a conservative flag. Without `data_gaps.gap_start_utc` I cannot choose.
**Leaning: data holes at exchange holidays/early closes, with a calendar-model false positive. UNVERIFIED.**

## 7. Findings table

| id | severity | file:line | evidence | fix |
|---|---|---|---|---|
| A1 | HIGH | `mt5_market.py:30-43` | `0 <= tick-(now+model) <= 5` accepts future ticks, rejects any tick ≥1 s old; prior P-1 `abs()` not applied; live +1.6 s skew masks it | use `abs(...) <= 5`; test −1/−5/−6/+5/+6 and negative skew |
| A2 | HIGH | `mt5_market.py:191-193` | naive server datetime → wrapper reads host-local; request 5400 s early on UTC+3:30 (prior live probe: −12600 s for naive UTC, −5400 s for +2 h); filter hides it, cap can exhaust before the window | pass `int(start_utc.timestamp())`; assert epoch in test |
| A3 | MEDIUM | `tests/unit/test_market_adapter.py:160-166` | calls a +30 s future tick "negative age"; no 1–5 s band, no small negative | rewrite direction-aware cases |
| A4 | MEDIUM | `tests/unit/test_market_adapter.py:132` | tick time frozen at construction; 1 s tick-over → estimator `None` → flaky | compute in `symbol_info_tick`; assert lag 2 / −2 / 30 |
| A5 | LOW | `market_data_service.py:240-246` | blocked tick attempt writes no `feed_runs` and no `time_sync` row | record a BLOCKED run + observed skew/samples |
| A6 | LOW | `mt5_market.py:102-120` | `set_server_offset` inert; `server_offset_s` returns the model | use it in conversion or remove |
| A7 | LOW | `approvals/` | no structured Phase 2 record; D-011 prose only | add A-07 |
| A8 | INFO | `evidence/pytest-…` | command `--tb=short`, not `-q`; 169 unverified | rerun with the stated command |
| A9 | INFO | `evidence/baseline-…` | `dirty: 57`, not 56; status count unverified | preserve a porcelain listing |

## 8. What I could and could not establish

**Verified by reading:** HEAD/branch; the exact fresh-tick predicate and all its call sites; the estimator's
arithmetic; the tick-window argument type; the F-B/F-C control flow and the single `insert_ticks` path; the
identity gate's fields; the scope clauses in the plan; the H1 gap rule in `quality.py`; the absence of a
holiday model; the test semantics.

**Inferred (not executed):** the HIGH `time_sync` row at 10:41Z (implied by `status: OK`); the 56→61 file
delta; the host-offset effect on `copy_ticks_from` (from the prior run's probe plus the current code's exact
arithmetic); the H1 data-vs-model judgement.

**Not performed (no execution tool):** `git status --porcelain`, `git diff`, `pytest`, `compileall`,
SHA-256, any SQLite query, any live MT5 probe.

**Not covered:** broker-clock behaviour across a DST switch; peak-rate tick runs; whether the 169-test
artifact corresponds to this exact tree; any consumer of stored ticks (none exists in `src/`).
