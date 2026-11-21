# Guardian trading-engine execution checklists

These are original Guardian-specific procedures derived from the reviewed MIT sources listed in ADOPTION_POLICY.md. They are not copied skill files and do not grant execution authority.

## Risk gate
1. Validate every numeric input as finite Decimal.
2. Calculate per-trade risk, daily loss, weekly loss, peak-to-current drawdown, aggregate open risk and consecutive losses.
3. Return an immutable structured decision with all blocking reasons.
4. Any invalid/missing input is a typed rejection; never treat missing state as zero or safe.
5. Unit-test exact boundaries, one-unit-over limits, non-finite values and multiple simultaneous breaches.
6. Never read broker account fields until A-04 exists.

## Backtest authenticity
1. Validate OHLC, timestamps, symbol, timeframe and spread before simulation.
2. Form signals only from closed bars; fill at the next bar open.
3. Include entry and exit spread, slippage, commission and stop/target gap behavior.
4. When OHLC cannot determine intrabar order, assume the adverse outcome.
5. Verify truncation invariance and future-corruption invariance.
6. Re-run at 1.5x, 2x and 3x costs; add size/liquidity-based impact before claiming cost realism.
7. Store data, config, code and random-seed fingerprints with each experiment.

## Robustness
1. Run at least 2,000 IID bootstrap paths and 2,000 moving-block paths for sizing-grade results.
2. Report p05/p25/p50/p75/p95 for total PnL and max drawdown.
3. Compare the original historical path with the bootstrap distribution.
4. Use chronological walk-forward; purge overlapping target horizons and embargo post-test rows.
5. Keep all attempted variants; never tune against test folds.

## Regime and operations
1. Use past-only trend efficiency and realized volatility relative to historical baseline.
2. Insufficient or unknown state is conservative: block or human review.
3. Define actions before deployment; regime labels do not autonomously change parameters.
4. Block new decisions on disconnect, missing/stale tick, invalid spread or outlier spread.
5. A latched kill switch cannot auto-reset; explicit owner approval is required.
6. No broker execution, cancellation, flattening or live-mode action is part of these domain modules.

## Verified learning
1. Preserve immutable source evidence and SHA-256.
2. Separate observation, hypothesis, experiment, decision, remediation and verification.
3. A lesson stays CANDIDATE until independent PASS and required owner approval.
4. Never auto-modify locked risk controls or permissions.
5. Rejected/deferred lessons cannot appear as active recommendations.
