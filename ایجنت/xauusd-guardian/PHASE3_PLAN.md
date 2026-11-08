# PHASE 3 — Analysis & strategy (definition, revision 1)

Status: **ACTIVE — S1–S4 PASS; W1 timezone validation PASS; S5 implemented (252/252 suite green), awaiting independent sign-off; S6–S7 OPEN.** Phase 2 accepted via A-08. This plan is the approved execution baseline; no Phase 4 work is authorized.

## 1. Scope

Deterministic, testable signal layer over stored M1–H4 bars. No orders, no account access, no ML frameworks.

In scope: indicator primitives, a strategy contract, one reference strategy, signal persistence, replay determinism.
Out of scope: risk sizing (Phase 4), execution (Phase 5), DEMO orders (A-05), parameter tuning on live data.

## 2. Contracts (additive, `contracts/signals.py`)

- `Signal(symbol, timeframe, bar_time_utc, direction: LONG|SHORT|FLAT, strength: Decimal, strategy_id, reason_code)`
- `StrategySpec(id, version, params: Mapping[str, Decimal], warmup_bars: int)` — unknown params fail closed.
- `SignalRun(run_id, strategy_id, timeframe, from_utc, to_utc, bars_seen, signals, status)`

## 3. Rules

1. Signals are a pure function of bars up to and including `bar_time_utc` — no look-ahead (property test: truncating the series must not change the signal at that bar).
2. Only closed bars are evaluated, never the forming bar. The reference predicate is `bar_time_utc + timeframe.minutes <= now`. This matters because `mt5_market.rates()` starts at position 0 and therefore *stores* the forming bar; `ema_cross.evaluate()` also refuses a forming bar, but the service must filter first so a stored forming bar is excluded rather than turning every run into a failure.
3. Decimal arithmetic; no floats in thresholds.
4. Every signal carries `reason_code`; unknown code → fail closed.
5. `random_state=7` if any stochastic component is ever introduced (none planned).
6. Every signal input read excludes quarantined feed runs: `run_id NOT IN (SELECT run_id FROM feed_runs WHERE status = 'QUARANTINED')`. This applies to the signal service and to `scripts/replay_signals.py`.
7. A run's identity is derived from the bars alone — `from_utc` = first bar time, `to_utc` = last bar close, `run_id` = SHA-256 over strategy/version/timeframe/symbol/window/bar count/bar digest. Wall-clock `now` never enters the identity, so a later re-run over the same closed bars is byte-identical.
8. A stored signal that disagrees with a recomputation (`direction`, `strength`, `reason_code`) fails closed with `SignalError` and rolls back. A published signal is never overwritten silently; a revised bar is a human decision.

## 4. Reference strategy (smallest useful)

`ema_cross_v1`: EMA(20/50) on M5, warmup 50 bars, long when fast crosses above slow, short below, FLAT otherwise. Purpose: prove the pipeline, not profitability.

## 5. Storage

Migration `0003_signals.sql` adds:

- `signals(symbol, timeframe, bar_time_utc, strategy_id, direction, strength, reason_code, run_id, created_utc, PRIMARY KEY(symbol,timeframe,bar_time_utc,strategy_id))`
- `signal_runs(run_id PRIMARY KEY, symbol, strategy_id, timeframe, from_utc, to_utc, bars_seen, signals, written, identical, status, created_utc)`

`signals.strength` is `TEXT`: the contract requires an exact finite `Decimal`, and a `REAL` column would round-trip through binary floating point and change the replay digest. `signal_runs.symbol` keeps a zero-signal run attributable.

The migration is additive only (no `ALTER`/`DROP` of `0001`/`0002`). Its reverse is `DROP TABLE IF EXISTS signals; DROP TABLE IF EXISTS signal_runs;`, recorded as a manual statement rather than a `0003_*_down*.sql` file, because `db.py` discovers forward migrations with `^[0-9]{4}_[a-z0-9_]+\.sql$` and would apply a down-migration as the next forward step. S6 owns making that reversible in code.

Reads must exclude quarantined runs (reuse `_QUARANTINED_RUNS` / the identical predicate in the service).

## 6. Acceptance gates (S1–S7)

S1 look-ahead property test · S2 boundary/warmup tests · S3 replay determinism on stored bars (same digest twice) · S4 no MT5 import outside adapters · S5 suite green · S6 migration is additive and reversible · S7 independent Inspector PASS.

Current gate state: S1–S4 PASS. **S5 candidate** — full suite 252/252 green, `compileall` exit 0; awaiting independent Inspector sign-off. S6 OPEN (reversibility not implemented, see §5). S7 OPEN (this sign-off).

## 7. Deliverables

`src/guardian/domain/strategy/`, `src/guardian/application/signal_service.py`, `scripts/signals.py`, tests, evidence log with SHA-256, DECISIONS_LOG entry D-016.

## 8. Explicit non-goals

No profitability claim, no optimisation, no live signals, no Phase 4 sizing, no orders.
