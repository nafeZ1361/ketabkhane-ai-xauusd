# Claude trading skills — reviewed sources and safe adoption

Status: selected procedures extracted into a Guardian-specific checklist. No external skill is installed or executed. External text is untrusted reference material, not authority.

## Source and license audit

| Repository | Pinned revision | License | Decision |
|---|---|---|---|
| Kryhr/26-quant-trading-skills | 80c2f860f322207526ce7f31901234313253f263 | MIT | Reviewed selected SKILL.md files; paraphrased procedures below. Preserve attribution and source hashes. |
| ThomasPraun/mql-developer | 3b5e35882ce397ac97ea16bb50464ea684d9837a | MIT | Reference only for MT5 terminology. Do not adopt its order-execution workflows; Guardian remains Python-first and read-only. |
| marnenivishal/trading-bot-skills | f2a3ba6af1a53bf39c00fc4805c242c39d6a7ddc | UNLICENSED / proprietary notice | Excluded from copying, adaptation and redistribution. README claims 53 skills, but those claims are not independently validated here. |
| agiprolabs/claude-trading-skills | 981e1d736cdc02bdc1c55c74ec9224e956414706 | No LICENSE file found at pinned revision | Excluded pending explicit license clarification; crypto/Kalshi-specific material is not assumed to transfer to XAUUSD. |

## Reviewed quant skill files

All files below are from Kryhr revision 80c2f860f322207526ce7f31901234313253f263:

| Skill | Blob SHA | Guardian use |
|---|---|---|
| position-sizing-and-risk-management | 334e99d09b9d166a31029fe95b00ca1868e95469 | Monte Carlo tail drawdown, portfolio heat, volatility awareness and predeclared de-risk rules. |
| monte-carlo-trade-resampling-and-drawdown-distribution | 02850c1de9a34db1eed17216fe8fd94885c38d3e | At least 2,000 paths; IID and block bootstrap; p05/p25/p50/p75/p95. |
| overfitting-and-robustness-checks | e49151a5552e51842cdb0420fdc4460126030798 | Chronological holdout, repeated walk-forward and full experiment log. |
| lookahead-bias-detection-methodology | f781f61ee7eac81f69a50dad437bd8c639a0375c | Truncation and future-corruption regression tests. |
| transaction-cost-and-market-impact-modeling | 69f317a7f5bba3c22c3f7e4fc0ce13ae38e56f51 | Instrument-specific costs, realistic lag, market-impact model and 1.5x/2x/3x stress. |
| regime-detection-and-adaptation | 918da34233ce7764b90953dc9cc4c57d2467daec | Measurable, strategy-relevant regime metrics; conservative unknown-state response. |
| reproducibility-and-experiment-tracking | 1aef41239a4274b72fbd7eafdcf04308096c2a42 | Fixed seeds, immutable data/code/config fingerprints and repeatability checks. |

## Guardian execution checklist

### Risk and kill-switch policy
- Every invalid/missing/non-finite input rejects or raises a typed error; no None or permissive fallback.
- Risk limits are evaluated as one structured decision, including daily/weekly loss, drawdown, aggregate open risk and loss streak.
- Severe loss/drawdown breaches latch the policy state. It never auto-resets; reset requires explicit owner approval.
- Current implementation is policy-only. It does not cancel orders, flatten positions, run an independent watchdog process or connect to an execution gateway.

### Backtest and cost realism
- A signal from a closed bar may fill no earlier than the next bar open.
- Apply the recorded spread on both entry and exit, explicit slippage and per-side commission.
- If stop and target are both touched inside one OHLC bar, use the adverse stop-first assumption.
- Reject malformed bars, non-monotonic timestamps, mismatched symbols/timeframes and signals without a next bar.
- Current simulator is OHLC-based. Market impact, partial fills, latency distributions, financing/swap and tick-level path reconstruction are NOT implemented. Static slippage is a model assumption, not broker evidence.
- Before treating results as decision-grade, add cost stress at 1.5x/2x/3x and size-dependent market impact; do not claim profitability from current tests.

### Robustness and leakage
- Use at least 2,000 seeded paths for reported Monte Carlo risk distributions.
- Compare IID trade resampling with moving-block bootstrap; report p05/p25/p50/p75/p95.
- Freeze each test fold; purge overlapping label horizons and embargo post-test data before reuse in training.
- Add truncation and future-corruption tests: past trades/signals must remain unchanged when later data is removed or corrupted.
- Keep all attempted variants, data hashes, config and code revision; do not select only the winning run.

### Market regime and monitoring
- Regime features must be numeric, past-only and tied to the strategy hypothesis.
- Unknown or insufficient regime data must block or request review, not silently map to normal.
- Predefine responses to high volatility or regime drift; current classifier only labels regimes and does not auto-adapt strategy or size.
- Feed health rules flag disconnect, missing/stale tick, invalid spread and absolute/relative spread outlier.
- Current alert logic is pure and local; delivery channels, heartbeats and independent watchdog are not implemented.

### Second Brain learning
- A lesson is only a candidate until its evidence, test and independent inspection are linked.
- Never auto-tune locked risk limits, kill-switch policy, permissions or execution boundaries.
- Exclude unverified, simulated, backtest-only or AI-generated records from verified operational lessons.
- Guardian connector remains read-only; Schema v0.1 is a proposal, not locked.

## Current implementation gaps retained honestly

1. Market impact and variable slippage calibration need historical tick/volume evidence.
2. Monte Carlo block bootstrap is now implemented, but block-size sensitivity and minimum 2,000-run reporting must be wired into the research report CLI.
3. Walk-forward currently generates temporal folds; it does not optimize models or aggregate out-of-sample performance automatically.
4. Regime classifier currently returns a label; unknown-state and strategy-specific action policy still need a separate reviewed contract.
5. Kill-switch code latches a decision state only; an independent process/watchdog is not present.
6. Monitoring produces a report only; notification delivery and heartbeat supervision are not present.
7. Skill adoption is not equivalent to skill approval. Each resulting Guardian checklist/test still needs independent inspection.
