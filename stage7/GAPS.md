# Stage 7 GAP Registry

Registered open and resolved gaps for the XAUUSD research system, governed by
AGENTS.md (AUDIT → FIX → TEST → VALIDATE → PASS → HUMAN CONFIRMATION).

Human Confirmation: APPROVED Decisions 8-A / 9-B / 10-A
BY: nafeZ1361
AT: 2026-10-08T10:55:27Z
SCOPE: stage7/GAPS.md (new), module/execution.py:53, module/config.py (docs only)

## GAP-001 — F-006: split_manifest.json record mismatch — OPEN

- Severity: MEDIUM
- Finding source: `.claude/skills/project-controller/SKILL.md` (KNOWN BLOCKERS)
- Affected artifacts: `stage7/evidence/run1/split_manifest.json` and
  `stage7/evidence/run2/split_manifest.json`
  (sha256 `435c12cd98d287ca0c8e16d9f1ca1ec8467a8e78cc3f1e7f9e616b4628e3cba4`,
  recorded in both `run_manifest.json` files)
- Generator: `stage7/pipeline.py` `split_manifest` record (written at
  `stage7/pipeline.py:551`)
- Decision: 8-A — document as GAP only; **no code change** on this branch.
- Status: **OPEN**
- Constraint: locked run1/run2 evidence is intentionally untouched; remediation
  requires a dedicated audited stage with fresh Human Confirmation.

## GAP-002 — F-004: Risk config duality — RESOLVED

- Severity: MEDIUM
- Finding: risk limits had two sources of truth — the hardcoded
  `RiskLimits(max_volume=1.0)` fallback in `module/execution.py:53` versus the
  `RiskLimits.from_env()` RISK_* environment contract used by `main.py:94`.
- Resolution (Decision 9-B, branch `fix/stage73-f004-riskconfig`):
  - `module/execution.py:53` default validator is now
    `RiskValidator(RiskLimits.from_env())` (fail-safe defaults).
  - The RISK_* contract is documented in `module/config.py` as the single
    source of truth (docs/comment only; no forced refactor).
  - `main.py` unchanged (already correct).
  - `module/execution.py:44` and `:52` (`TRADING_MODE`, `ENABLE_LIVE_TRADING`)
    intentionally unchanged: their construction-time env reads are load-bearing
    for the test suite (patch.dict mode tests) and are execution-mode gating,
    not risk config.
- Fix commit: `222b76b3d4656b6d14f64633b9d6c931f7b3d409`
  (`fix(f004): construct default risk validator via RiskLimits.from_env()`)
- Status: **RESOLVED** (pending full-suite re-validation and separate Human
  Confirmation to merge)

## GAP-003 — Time-of-Day regime — OPEN (RESEARCH GAP)

- Type: RESEARCH GAP
- Target stage: Stage 7.2/8
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-004 — ATR/Volatility regime — OPEN (RESEARCH GAP)

- Type: RESEARCH GAP
- Target stage: Stage 8
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-005 — Monte Carlo trade-sequence — IMPLEMENTED (VALIDATION GAP)

- Type: VALIDATION GAP
- Target stage: Stage 8
- Implementation: stage8/monte_carlo.py (iid bootstrap, seed pcg64-v1, base_seed=42, 2000 replicates); evidence: stage8/evidence/monte_carlo_summary.json; tests: tests/test_stage8_validation.py
- Status: **IMPLEMENTED** — Verdict: no-edge, not bad luck. P(final PnL > 0) = 0.0; median maxDD ≈ -49.3% of equity on run1 holdout trades at baseline cost 0.30 USD.

## GAP-006 — Parameter landscape — IMPLEMENTED (VALIDATION GAP)

- Type: VALIDATION GAP
- Target stage: Stage 8
- Implementation: stage8/landscape.py (pre-registered grid: cost {0.00,0.20,0.30,0.50} × threshold {0.50,0.55,0.60}); evidence: stage8/evidence/landscape_summary.json (baseline cell reproduces run1 byte-exact, status PASS)
- Status: **IMPLEMENTED** — thr=0.60 cells positive across all cost levels (PF 1.51–1.62, only 478 trades). CAVEAT: selection on same holdout ⇒ NOT an edge claim until fresh out-of-sample test.

## GAP-007 — Slippage/execution friction — IMPLEMENTED (VALIDATION GAP, HIGH PRIORITY)

- Type: VALIDATION GAP
- Priority: HIGH — Stage 8, before any filter work
- Rationale: Stage 7.1 post-cost result is negative; validate friction first.
- Implementation: cost grid inside stage8/landscape.py (per-trade friction 0.00–0.50 USD)
- Status: **IMPLEMENTED** — Edge evaporates with friction at thr=0.50 (net -49k at 0.30); thr=0.60 survives up to 0.50 USD but sample is tiny (478 trades).

## GAP-008 — OFI/Depth Skew — OPEN (RESEARCH CANDIDATE)

- Type: RESEARCH CANDIDATE
- Target stage: Stage 7.2
- Dependency: L2/L3 data
- Implementation: none ("no impl")
- Status: **OPEN**
