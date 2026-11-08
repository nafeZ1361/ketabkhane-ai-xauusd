# AUDIT-PHASE1-FINAL — closing verification of the Phase 1 tree

**Auditor:** independent reviewer (read-only). **Date:** 2026-11-04.
**Tree:** `master` @ `82ab8b5` + working tree (11 modified, 13 untracked paths); no commit made.
**Baseline:** five closing checks in the task brief; prior audits `reports/AUDIT-PHASE1-D003.md` and
`reports/AUDIT-PHASE1-REMEDIATION.md` (F1–F4 closed, W1/W2 open at that time).
**Method:** execution. Probes run out-of-repo (`%TEMP%\audit_final_probe.py`, `audit_final_e2e.py`,
`audit_ast_final.py`, `audit_gate_probe.py`); `preflight.main()` executed twice with `ROOT` redirected to a
temp tree, so no evidence file was written inside the repo.

## 1. Verdict

All five closing checks pass. No must-fix finding. Two worth-considering items, both residuals in the new
company enforcement rather than regressions: a blank `expected_company` silently disables the check, and the
`preflight` wiring of that value has no test.

| # | Check | Result |
|---|---|---|
| 1 | `expected_company` enforced end-to-end | **PASS** |
| 2 | `reject_on_mismatch = false` rejected | **PASS** |
| 3 | Full suite, exact numbers | **PASS** |
| 4 | AST order-API scan of touched modules | **PASS** |
| 5 | No non-identity policy can produce gate PASS | **PASS** |

## 2. Evidence per item

### 1 — PASS

Service-level probes with the shipped profile (`configs/config.toml` → `expected_company = 'Aron Markets Ltd'`):

```
(company="Another Broker Ltd") status=CONNECTION_FAILED ok=False gate_failed=True
                               symbol=None reason=company is 'Another Broker Ltd', expected 'Aron Markets Ltd'
(control, real identity)       status=VERIFIED          ok=True  gate_failed=False symbol=XAUUSD.
```

End-to-end `preflight.main()` against a temp `ROOT` (config copied verbatim), live terminal MT5 5.0.6231 /
build 6230:

- adapter identity stubbed to `company="Evil Broker Ltd"` → `account_mode BLOCKED ("company is 'Evil Broker Ltd',
  expected 'Aron Markets Ltd'")`, `symbol_resolution NOT CHECKED`, `spread_points NOT CHECKED`, exit **2**,
  evidence `exit_code=2`.
- unpatched run against the live account → `account_mode PASS (DEMO)`, `symbol_resolution VERIFIED`
  (`XAUUSD.`, exact identity corroborated), `spread_points [15, 15, 15]`, exit **0**.

So the correct company still yields VERIFIED, and a mismatch is refused before any symbol work.

### 2 — PASS

`parse_settings` with `[account].reject_on_mismatch = false`:

```
ConfigError: [account].reject_on_mismatch must be true; mismatch handling is fail-closed and is not configurable
```

Guard `_require_true` (`settings.py:120-127`, applied at `settings.py:272`) also rejects non-bool values and a
missing key; `tests/unit/test_config.py:149-152` covers the false case and passes.

### 3 — PASS

```
90 passed in 1.43s          (exit 0, `.\.venv\Scripts\python.exe -m pytest`)
JUnit XML: tests=90 failures=0 errors=0 skipped=0 time=2.056
```

Per module: boundaries 5, config 22, logging 6, reporting 4, storage 6, identity 15, investigation 10,
service 13, symbols 9. Delta vs the 88 of the prior audit is exactly +1 config and +1 service, matching
the two claimed new tests.

### 4 — PASS

AST scan of the three touched production modules (`src/guardian/application/symbol_service.py`,
`src/guardian/config/settings.py`, `scripts/preflight.py`): no `order_send`, `order_check`,
`order_calc_*`, `positions_*`, `orders_get`, `history_orders_get`, and no order-shaped dict
(`{action, symbol, volume}`). Repo-wide scan of the remaining 9 modules under `src/guardian` also clean for
those names; the only `margin` hits are `SymbolResolution.margin` (score gap, `schemas.py:136`) and local
score variables (`symbols.py:278-299`), not account margin. `tests/security/test_boundaries.py`
(`test_no_forbidden_trade_calls_anywhere`, `test_adapters_never_touch_sensitive_account_fields`) passes.

### 5 — PASS

- `SymbolResolution.ok` is `self.status is ResolutionStatus.VERIFIED` (`schemas.py:144`).
- The only `ResolutionStatus.VERIFIED` construction in the tree is `symbols.py:219`, inside
  `_resolve_by_identity`, which hard-codes `policy=IDENTITY_POLICY`; `identify_gold_symbol` dispatches to it
  only when `policy == IDENTITY_POLICY` (`symbols.py:241-242`). Legacy policies go through `_POLICY_FILTERS`.
- `preflight` maps only `VERIFIED → ("PASS", 0)`, defaults everything else to `("BLOCKED", 2)`, and adds a
  policy guard: `if resolution.ok and resolution.policy != IDENTITY_POLICY: label, code = "BLOCKED", 2`
  (`preflight.py:144-146`).
- Probe on the captured live table: `xauusd_strict_v1` → `AMBIGUOUS ok=False`; `spot_metal_usd_v2` →
  `RESOLVED ok=False`; `xauusd_identity_v3` → `VERIFIED ok=True`. `VERIFIED is not RESOLVED` → `True`.

## 3. Must fix

None.

## 4. Worth considering

**W1 — a blank `expected_company` silently switches the company gate off.**
`src/guardian/config/settings.py:270` accepts `expected_company = ""` (plain `_get(..., str, ...)`), and
`src/guardian/application/symbol_service.py:62` guards the comparison with `if self._expected_company and ...`.
Probe: `expected_company=""` with identity `company="Another Broker Ltd"` → `VERIFIED`, `ok=True`.
Impact: the profile claims fail-closed mismatch handling (`reject_on_mismatch` is pinned true) yet one blank
value yields a gate PASS without company corroboration; the operator gets no warning. Scope is limited
because `configs/config.toml` is already a trust anchor (expected_server can be edited the same way), so this
is consistency, not a new privilege boundary. Fix: reject empty/whitespace `expected_company` in the loader
(as `expected_trade_mode` is pinned to `DEMO`), or compare unconditionally and let an empty expectation fail.

**W2 — `preflight`'s company wiring is untested.**
`scripts/preflight.py:114` passes `expected_company=settings.account.expected_company`, but no test imports
`scripts/preflight.py`; the only company test calls the service directly
(`tests/unit/test_symbol_service.py:175-181`). Deleting that keyword argument leaves all 90 tests green, so a
future refactor could silently reinstate F5. Fix: one preflight-level test with a fake adapter (or patched
`account_identity`) asserting exit 2 and `account_mode BLOCKED` on a company mismatch.

## 5. Notes

- Prior W1 closed: `CHANGELOG.md:15` now reads "`RESOLVED` is retired as a distinct, non-permissive value
  (never an alias of `VERIFIED`)", consistent with the runtime and with line 23.
- `reject_on_mismatch` is parsed and stored (`settings.py:58,272`) but never read by the service or
  `preflight`; enforcement is entirely at load time. Harmless today, but the field is declarative only.
- `preflight.py:166` still hardcodes evidence `"schema_version": 1` while the contract `SCHEMA_VERSION` is 2 —
  carried over from the prior audit, not touched by this delta.
- Delta scope could not be diffed from VCS (the prior audit snapshot was never committed; `src/guardian/application/`
  is untracked as a whole directory). File mtimes corroborate the claimed scope: after 21:16 only
  `scripts/preflight.py` (21:30), `symbol_service.py` (21:31), `settings.py` + two tests (21:32) and
  `CHANGELOG.md`/`PROJECT_STATE.md` (21:34) changed.
- `PROJECT_STATE.md:49` claims "90 passed in 1.44s"; observed 1.43s — consistent.

## 6. Scope and what was not covered

**Executed:** three service-level probes (mismatch, correct-company control, blank-company), two loader probes
(`reject_on_mismatch=false`, `expected_company=""`), two full suite runs (plain + JUnit XML), two AST scans
(touched modules and repo-wide), a three-policy domain gate probe, and two end-to-end `preflight.main()` runs
(stubbed company mismatch; live unpatched control) with `ROOT` in `%TEMP%`.

**Not verified:** no second real broker account exists, so the mismatch was synthesized at the adapter
identity boundary rather than observed on a live wrong-company terminal. No commit was made and no evidence
file was written inside the repo. Balance/equity/margin were never read; the boundary test asserting the
adapter exposes no such fields passes.

