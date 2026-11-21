# PHASE 4 — Risk (definition, revision 1)

Status: **AUTHORISED 2026-11-21** (owner mission "FINISH & PUBLISH"). Scope limited to the
pre-registered slice in `DECISIONS_LOG.md` D-023. No account access, no orders, no MT5.

## 1. Scope

A pure, deterministic position-sizing function. It answers one question only:
*for this equity, this risk fraction and this stop distance, how many lots?*

In scope:

- `RiskSpec` (frozen dataclass): `risk_fraction`, `value_per_point_lot`, `lot_step`, `min_lot`,
  `max_lot` — all `Decimal`.
- `position_size(equity, stop_points, spec) -> Decimal`.
- `RiskError` for every inconsistent or non-finite input (fail closed).

Out of scope (unchanged): account access (`A-04` not requested), order construction (`A-05`),
`MetaTrader5`, portfolio/correlation limits, kill switches, Phase 5, changes to accepted strategy
or risk rules, migrations `0001`–`0003`.

## 2. Contract

| Item | Rule |
|---|---|
| Input types | `Decimal` only; `float`/`int` are refused (no binary drift) |
| Equity | must be a positive finite `Decimal` |
| Stop | positive finite `Decimal`, in points |
| `risk_fraction` | `0 < f < 1` |
| `lot_step`, `min_lot` | positive; `min_lot` must be a multiple of `lot_step` |
| `max_lot` | `>= min_lot` |
| Result | `min ≤ result ≤ max`, a multiple of `lot_step`, rounded **down** |
| Risk bound | `result × stop × value_per_point_lot ≤ equity × risk_fraction` |
| Fail closed | `RiskError`; never a silent 0.0 or a best-effort guess |

## 3. Acceptance gates (S1–S6, frozen in D-023 before code)

S1 risk bound over a numeric grid · S2 step multiple and cap · S3 monotonicity · S4 fail-closed
matrix · S5 no trading surface in the module (AST/source scan) · S6 suite + `compileall` green.
Acceptance additionally requires an independent PASS on the exact snapshot (S7) — this cannot be
self-issued.

## 4. Non-goals

No profitability claim. No sizing advice. No connection between this function and any order path —
the function returns a number and nothing else.
