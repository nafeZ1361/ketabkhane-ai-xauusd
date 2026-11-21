# Guardian and repository audit — 2026-11-21

Audit base: 907f4e37ce63ce2b28a33cb5132d70831032a56e
Current remediation head at report update: 1340564b76e1bafb876d460778a74e4c418fb632
Branch: work/guardian-risk-research-second-brain-audit
Scope: Guardian subtree plus root CI/test wiring. Phase 1–4 acceptance records were not reopened.

## Confirmed findings and remediation

| ID | Severity | Evidence | Confirmed issue | Change |
|---|---|---|---|---|
| G-01 | High | Guardian src/guardian/domain/risk/sizing.py:44; tests/unit/test_risk_sizing.py | When computed size exceeded an unaligned max_lot, the old cap branch could return a non-multiple of lot_step. | Cap is floored to lot_step; regression tests cover 0.505 cap and risk bound. |
| G-02 | High | Guardian README.md; HANDOFF/00_READ_ME_FIRST.md; HANDOFF/01_STATE_SNAPSHOT.md; HANDOFF/02_ROADMAP.md | Handoff said Phase 3 was in progress / Phase 4 unauthorized, contradicting PROJECT_STATE and D-022/D-024. | Current entry pages synchronized; historical evidence retained. |
| G-03 | High | PHASE4_PLAN.md §1; D-023 | Accepted Phase 4 intentionally only implements pure per-trade sizing; no daily/weekly loss, aggregate open risk, equity drawdown or kill-switch contract existed. | Added synthetic-input RiskLimits/RiskSnapshot decision engine and latched policy-only kill switch. No account data or order path. |
| G-04 | High | scripts/research_edge.py; D-018/D-021 | Existing ML research is a chronological holdout experiment, not an execution backtester. It lacks order timing, stop/target fills, per-bar spread path, slippage, commission and trade-equity path. | Added separate OHLC event-driven simulator with next-bar fills, spread, slippage, commission, stop/target and adverse stop-first same-bar assumption. |
| G-05 | Medium | src/guardian/domain/market/quality.py; MarketDataService | Existing code already checks OHLC, duplicates, gaps, stale bars and crossed quotes. A concise tick-age/spread/connection alert policy was missing. | Added pure FeedHealthSnapshot evaluator; no delivery channel or external watchdog. |
| G-06 | Medium | requirements.lock; D-004/D-021 | ML experiment uses pandas/scikit-learn while runtime dependency policy remains stdlib-first and research tests are deferred. | No runtime dependency added; research experiment remains isolated. |
| G-07 | High (CI reliability) | Root tests/test_a4_pipeline.py; src/xauusd_research/schema.py:109; .gitignore; root README | A4 tests read data/sample_300k.tsv, but all data/* is gitignored and README identifies tests/fixtures/synthetic_500.csv as the committed fixture. Clean CI therefore failed 2 tests on Python 3.10 and 3.12. | A4 tests now use the committed deterministic fixture and assert it exists. Root CI now passes on both versions. |

## Implemented research modules

- Risk: src/guardian/domain/risk/controls.py:49; kill_switch.py:34. Synthetic caller-supplied values only.
- Backtest: src/guardian/research/backtest.py:76. OHLC model; not tick-level execution.
- Monte Carlo: src/guardian/research/robustness.py:35. 2,000-run default, IID and moving-block bootstrap, drawdown amount/fraction, p05/p25/p50/p75/p95.
- Walk-forward: src/guardian/research/walkforward.py:13. Expanding chronological fold generator with purge/embargo; no optimizer/metric aggregator.
- Regime: src/guardian/research/regimes.py:30. Past-only trend efficiency and volatility label; no automatic adaptation.
- Monitoring: src/guardian/domain/market/health.py:41. Pure stale tick, invalid/outlier spread and connection checks; no alert delivery.

## Skill provenance

- Selected procedures paraphrased from Kryhr/26-quant-trading-skills, pinned MIT revision 80c2f860f322207526ce7f31901234313253f263. Exact SKILL.md hashes and Guardian checklists are in docs/claude-skills/.
- marnenivishal/trading-bot-skills is marked UNLICENSED/proprietary; no content copied or adapted.
- ThomasPraun/mql-developer is MIT and reference-only; no MQL order code adopted.
- agiprolabs/claude-trading-skills had no LICENSE file at inspected revision and is excluded pending license clarification.

## Second Brain

docs/second-brain/SCHEMA_PROPOSAL_v0.1.md is a design proposal only. No Second Brain repository was present in the connected GitHub repository inventory. No Layer 1 implementation, database, connector or learner was created. The exact owner command قفل Schema v0.1 remains the gate.

## CI evidence at current head 1340564b76e1bafb876d460778a74e4c418fb632

- Guardian Windows / Python 3.11: 359 tests passed (progress-dot count), exit success; compileall step succeeded. Run: https://github.com/nafeZ1361/ketabkhane-ai-xauusd/actions/runs/44933297489
- Root project Python 3.10: 121 passed, 0 failed, 0 errors; coverage 95.77%. Run: https://github.com/nafeZ1361/ketabkhane-ai-xauusd/actions/runs/44933297549
- Root project Python 3.12: 121 passed, 0 failed, 0 errors; coverage 95.77%. Same matrix run above.
- CI is not independent inspection. No independent Inspector PASS is claimed for this branch.

## Explicit residuals / non-claims

1. Backtest still lacks market impact, partial fills, variable latency, financing/swap and tick-level path. Static slippage is an assumption; spread comes from supplied bars.
2. Backtest drawdown is closed-trade equity drawdown, not tick-by-tick intratrade maximum drawdown.
3. Monte Carlo supports IID and moving blocks; sizing-grade reports still need frozen trade data and code/config hashes.
4. Walk-forward creates folds only; model fitting, parameter freezing and aggregated out-of-sample metrics are not automated.
5. Regime classifier labels trend/range/high volatility; it does not emit a validated UNKNOWN regime policy or change strategy/size.
6. Kill switch is a policy latch only; no independent watchdog process, broker cancel or position flattening.
7. Monitoring is a pure local report; no Telegram/email/UI delivery or independent heartbeat service.
8. No A-04 account data, A-05 order operations, broker credentials, live mode or live orders were added.
9. Phase 3 D-022 and Phase 4 D-024 remain accepted; D-019 remains deferred. PHASE2-CLOCK-RECHECK-1 remains a separate ticket per D-025.
10. Independent frozen-snapshot inspection is still required. If a separate read-only identity cannot be proven, verdict must be INDEPENDENCE_NOT_ESTABLISHED.
