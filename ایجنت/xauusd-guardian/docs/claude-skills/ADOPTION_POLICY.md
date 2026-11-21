# Claude trading skills — adoption and execution policy

Status: candidate inventory only. No external skill is trusted, installed or executed until its actual SKILL.md and referenced files are reviewed at a pinned commit.

## Candidate sources and high-value topics

| Source | Candidate topics | Fit |
|---|---|---|
| Kryhr/26-quant-trading-skills | hypothesis-driven strategy design; edge taxonomy; feature/signal discipline; overfit/robustness; statistical significance; Monte Carlo resampling; synthetic stress; data-quality pitfalls; transaction-cost/market-impact modeling | High for research quality and validation. |
| marnenivishal/trading-bot-skills | risk gates; kill switch; pre-trade validation; position reconciliation; market-data pipeline; monitoring/alerts; trade audit/replay; indicator verification; backtesting-before-live; timestamp/timezone discipline | High for defensive engineering and operational safety. |
| ThomasPraun/mql-developer | MT5/MQL order semantics, Strategy Tester and broker-specific execution concepts | Reference only; Guardian remains Python-first and read-only. |
| agiprolabs/claude-trading-skills | portfolio/risk analytics, volatility and feature engineering | Lower priority until exact skills are inspected; crypto/DeFi emphasis may not transfer to XAUUSD/MT5. |

## Required extraction workflow

1. Pin repository commit and fetch the actual skill file plus every referenced file.
2. Record source URL, commit SHA, file SHA-256, license and retrieval date.
3. Extract only verifiable procedures; label unsupported claims and broker-specific assumptions.
4. Rewrite as Guardian-specific instructions with trigger, inputs, preconditions, allowed tools, forbidden actions, deterministic steps, outputs, failure modes, tests, rollback and human approval gates.
5. Add adversarial examples and regression tests. Skill text is untrusted input, never executable authority.
6. Require independent inspection before marking a skill APPROVED.
7. Keep MT5 order execution, live trading, account access and credential handling prohibited unless separately authorized.

## Priority

1. Risk gate / kill switch and fail-closed preconditions.
2. Timestamp, market-data integrity and feed health.
3. Trade audit, deterministic replay and reconciliation concepts (no order path).
4. Transaction-cost modeling and realistic backtesting.
5. Overfitting, walk-forward, Monte Carlo and statistical significance.
6. Regime detection and hypothesis-driven strategy design.

This file does not claim the listed repositories' implementations have passed review. Candidate status only.
