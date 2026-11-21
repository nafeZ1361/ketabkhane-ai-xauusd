# Guardian repository audit — 2026-11-21

Base revision: 907f4e37ce63ce2b28a33cb5132d70831032a56e
Audit branch: work/guardian-risk-research-second-brain-audit
Scope: read-only source inspection before remediation. No accepted phase was reopened.

## Confirmed findings

| ID | Severity | Evidence | Finding | Remediation |
|---|---|---|---|---|
| G-01 | High | src/guardian/domain/risk/sizing.py, position_size(); tests/unit/test_risk_sizing.py | If max_lot is not a multiple of lot_step, the cap branch returned the invalid raw cap. Existing test used only aligned 0.50. | Floor the cap to a valid lot-step multiple; add regression tests. |
| G-02 | High (operator confusion) | README.md; HANDOFF/00_READ_ME_FIRST.md; HANDOFF/01_STATE_SNAPSHOT.md; HANDOFF/02_ROADMAP.md | Handoff pages described Phase 3 as in progress and Phase 4 unauthorized, while PROJECT_STATE.md and D-024 record both accepted. | Synchronize current handoff guidance; preserve historical evidence. |
| G-03 | High (scope gap) | PHASE4_PLAN.md §1 and D-023 | Accepted Phase 4 deliberately covers pure per-trade sizing only. Portfolio/day/week loss caps, equity-curve drawdown controls, aggregate open risk and emergency stop are outside that contract. | Add a separate synthetic-input risk-gate design; do not read account data until A-04. |
| G-04 | High (research validity) | scripts/research_edge.py; D-018/D-021 | The script is a single chronological holdout ML experiment, not an event-driven execution backtester. It does not simulate order timing, stop/target execution, spread path, slippage, commission or equity/drawdown path. D-018 explicitly corrects the label “walk-forward”. | Keep it isolated. Build a deterministic event-driven simulator with explicit costs and adverse intrabar ordering. |
| G-05 | Medium | src/guardian/domain/market/quality.py; MarketDataService | Bar-quality checks already cover stale bars, duplicates, gaps, malformed OHLC and crossed quotes. A full alert policy for stale ticks, spread outliers and connection transitions is not evidenced by these modules. | Add pure alert rules using synthetic snapshots; keep MT5 read-only. |
| G-06 | Medium | requirements.lock; D-004/D-021 | Runtime dependencies are constrained. Research script imports pandas and scikit-learn; its research tests are out of scope / NOT_RUN under D-021. | Do not add these to Guardian runtime. Keep optional research environment separate and approved. |

## Explicit limits

- Existing numpy lock entry is a transitive MT5 dependency; it is not evidence pandas or scikit-learn are installed.
- The risk module is pure and intentionally does not call account_info. A-04 remains ungranted; no account Equity/Balance access is added.
- quality.py already implements bar freshness and OHLC/tick sanity checks. Do not duplicate these checks.
- No event-driven trade simulator, Monte Carlo drawdown engine or sequential walk-forward runner was found in inspected files. This is a bounded source audit, not proof about every repository file.
- Phase 3 (D-022) and Phase 4 (D-024) remain accepted. D-019 remains deferred. Phase 2 clock recheck remains separate per D-025.
- No order API, live mode, broker credential, database migration or account data access is introduced by this audit.

## Verification status

This report records source findings, not test execution. New regression tests require Windows CI and independent inspection of a frozen commit. No PASS is pre-claimed.
