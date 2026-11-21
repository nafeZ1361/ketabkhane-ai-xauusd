# Monte Carlo risk engine (D-026)

Status: **implemented and tested; acceptance pending independent inspection (S11)**.
Scope fixed in `DECISIONS_LOG.md` D-026 **before** the code was written.

## 1. What it is

A resampling engine over a sequence of per-trade **R multiples** (profit or loss as a
multiple of the amount risked on that trade). It answers: *if this trade sequence were
replayed in a different order — or in blocks that preserve short runs — how bad could the
drawdown and ruin outcomes look?*

It is **not** a forecast and **not** a trading system. It re-uses observed trades; it cannot
invent a regime the sample never contained.

## 2. Method

| Element | Implementation |
|---|---|
| Resampling | IID (with replacement) or **moving block bootstrap**: contiguous, wrapping runs of `block_size` trades |
| Path length | one synthetic history = the observed number of trades |
| Sizing | risk = `risk_fraction × equity_at_that_moment` (dynamic; a losing run shrinks size) |
| Costs | `cost_r` subtracted from every trade, multiplied by the stress factor (1×/1.5×/2×/3×) |
| Drawdown | peak-to-trough on the equity path; distribution and threshold-exceedance probabilities |
| Ruin | explicit: `equity ≤ initial_equity × (1 − ruin_fraction)` (also true at `equity ≤ 0`); the path stops |
| Sensitivity | Bernoulli grid over shifted win rate and scaled payoff (RR), seeded per cell |
| Comparison | several strategies under the same spec and seed |
| Arithmetic | `Decimal` throughout; `float` inputs are refused |
| Randomness | `random.Random(seed)` only — reproducible, no platform-dependent RNG |

## 3. Inputs and outputs

Input JSON (either shape):

```json
{"strategies": {"name": [1.5, -1.0, 0.8]}}
```
or a bare list of R multiples.

```powershell
.\.venv\Scripts\python.exe scripts\montecarlo.py --input trades.json --out report \
  --sims 2000 --seed 7 --mode block --block-size 5 \
  --risk 0.01 --ruin 0.5 --cost-r 0.02 --cost-multipliers 1,1.5,2,3
```

Outputs `report.json` (parameters, seed, input SHA-256, software revision, results,
assumptions, `content_sha256`) and `report.md` (tables). The digest excludes only the
`generated_utc` field, so identical inputs reproduce the same digest.

## 4. Assumptions and limitations (stated in every report)

- The sample is assumed representative; unseen regimes are invisible.
- IID mode destroys serial dependence; block mode preserves runs of `block_size` only.
- Costs are a fixed R amount; no slippage curve, no liquidity model, no spread dynamics.
- Sensitivity assumes independence and stable payoff magnitudes — it is a model, not data.
- Ruin is an equity threshold, not a broker margin call.
- Results are **risk descriptions**, never predictions or guarantees.

## 5. Safety

No `MetaTrader5`, no account read, no order construction, no network. Pure functions over
caller-supplied numbers. Enforced by an AST test in `tests/unit/test_montecarlo.py`.

## 6. Files

| Path | Role |
|---|---|
| `src/guardian/domain/risk/montecarlo.py` | engine (`MonteCarloSpec`, `simulate`, `compare_strategies`, `sensitivity`, `canonical_digest`) |
| `scripts/montecarlo.py` | CLI + reproducible JSON/Markdown report |
| `tests/unit/test_montecarlo.py` | 30 tests covering the D-026 criteria |
