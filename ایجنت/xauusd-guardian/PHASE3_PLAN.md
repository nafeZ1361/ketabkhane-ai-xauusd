# PHASE 3 — Analysis & strategy (definition, revision 1)

Status: **ACTIVE — S1–S4 PASS; W1 timezone validation PASS; S5–S7 OPEN.** Phase 2 accepted via A-08. This plan is the approved execution baseline; no Phase 4 work is authorized.

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
2. Only closed bars are evaluated (`last_seen_utc < now`), never the forming bar.
3. Decimal arithmetic; no floats in thresholds.
4. Every signal carries `reason_code`; unknown code → fail closed.
5. `random_state=7` if any stochastic component is ever introduced (none planned).

## 4. Reference strategy (smallest useful)

`ema_cross_v1`: EMA(20/50) on M5, warmup 50 bars, long when fast crosses above slow, short below, FLAT otherwise. Purpose: prove the pipeline, not profitability.

## 5. Storage

Migration `0003_signals.sql`: `signals(symbol, timeframe, bar_time_utc, strategy_id, direction, strength, reason_code, run_id, PRIMARY KEY(symbol,timeframe,bar_time_utc,strategy_id))` + `signal_runs`. Reads must exclude quarantined runs (reuse `_QUARANTINED_RUNS`).

## 6. Acceptance gates (S1–S7)

S1 look-ahead property test · S2 boundary/warmup tests · S3 replay determinism on stored bars (same digest twice) · S4 no MT5 import outside adapters · S5 suite green · S6 migration is additive and reversible · S7 independent Inspector PASS.

## 7. Deliverables

`src/guardian/domain/strategy/`, `src/guardian/application/signal_service.py`, `scripts/signals.py`, tests, evidence log with SHA-256, DECISIONS_LOG entry D-016.

## 8. Explicit non-goals

No profitability claim, no optimisation, no live signals, no Phase 4 sizing, no orders.
