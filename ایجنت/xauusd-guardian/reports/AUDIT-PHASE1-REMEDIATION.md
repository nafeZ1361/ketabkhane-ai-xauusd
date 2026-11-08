# AUDIT-PHASE1-REMEDIATION — remediation cycle 1 recheck (F1–F4 + regression)

**Auditor:** independent reviewer (read-only). **Date:** 2026-11-04.
**Tree:** `master` @ `82ab8b5` + working tree (11 modified, 6 new test/modules).
**Baseline:** findings F1–F4 of `reports/AUDIT-PHASE1-D003.md`; brief's probe list for this cycle.
**Method:** execution, not diff reading. Live MT5 5.0.6231 / terminal build 6230 / 575 symbols; probes
run out-of-repo (`%TEMP%\audit_recheck.py`, `audit_e2e_legacy.py`, `audit_ast.py`, `audit_meta.py`);
`preflight.main()` executed end-to-end with `ROOT` redirected to a temp tree so no repo evidence was written.

## 1. Verdict

All four findings are closed and the regression legs hold. No must-fix item found. Two documentation
inconsistencies and four observations are recorded below; none blocks acceptance of this remediation.

| Item | Result |
|---|---|
| F1 scoring policy cannot pass the gate | **PASS** |
| F2 bare `XAUUSD` cannot verify | **PASS** |
| F3 account refusal → `account_gate_failed` / exit 2 | **PASS** |
| F4 unknown policy → `ValueError` | **PASS** |
| Regression (metadata, suite, AST order scan) | **PASS** |

## 2. Evidence per finding

### F1 — PASS

- `ResolutionStatus.RESOLVED is ResolutionStatus.VERIFIED` → `False`; `==` → `False`;
  `__members__` has six distinct keys, `SCHEMA_VERSION = 2` (`schemas.py:56-64`).
- Only one `VERIFIED` construction exists in the domain: `symbols.py:219`, inside `_resolve_by_identity`.
- Live 575-symbol table, shipped expectations (`aliases=("XAUUSD.",)`, `required_symbol_name="XAUUSD."`):

```
xauusd_strict_v1   status=AMBIGUOUS  ok=False  name=None      label=('BLOCKED', 2)
spot_metal_usd_v2  status=RESOLVED   ok=False  name=XAUUSD.   label=('BLOCKED', 2)
single winner (strict, XAUUSD.m only) status=RESOLVED ok=False label=('BLOCKED', 2)
```

- End-to-end `preflight.main()`, shipped config copied verbatim, only `symbol_policy` overridden:
  `spot_metal_usd_v2` → exit **2**, evidence `exit_code=2`, `symbol_resolution BLOCKED / RESOLVED`;
  `xauusd_strict_v1` → exit **2**. Defense-in-depth guard verified with a synthesized
  `VERIFIED` + `spot_metal_usd_v2` resolution → `('BLOCKED', 2)`.

### F2 — PASS

- Shipped config vs a table containing only bare `XAUUSD` → `NOT_FOUND`, `ok=False`,
  `reason="no symbol matched the exact alias list ['XAUUSD.']"`, label `('BLOCKED', 2)`; end-to-end exit **2**.
- Widened `aliases=("XAUUSD","XAUUSD.")` → `METADATA_MISMATCH`,
  `mismatches=(('symbol_name','XAUUSD.','XAUUSD'),)`, `ok=False`.
- Widened aliases with both names present → `AMBIGUOUS`. Control: shipped config on live table → `VERIFIED`, `('PASS', 0)`.

### F3 — PASS

- Service with REAL identity → `CONNECTION_FAILED`, `account_gate_failed=True`,
  reason `account trade_mode is 'REAL', expected 'DEMO'`; same for wrong server.
- End-to-end `preflight.main()` with REAL identity → exit **2**, checks
  `account_mode=BLOCKED`, `symbol_resolution=NOT CHECKED`, `spread_points=NOT CHECKED`, evidence `exit_code=2`.
  Control (DEMO + valid `XAUUSD.`) → exit **0** with `symbol_resolution=PASS`, so the PASS path still exists.

### F4 — PASS

- `SymbolResolverService(policy="nonsense_policy").resolve()` → raises `ValueError: unknown symbol policy: 'nonsense_policy'`;
  adapter still detached in `finally`.
- Generic adapter fault (`RuntimeError` in `symbol_specs`) → `CONNECTION_FAILED "terminal read failed: ipc died"`,
  so the distinction is real and not a blanket re-raise.
- Loader rejects the same policy with `ConfigError`; registry is single-sourced
  (`settings.py:21-23`, `KNOWN_SYMBOL_POLICIES = KNOWN_POLICIES`).

### Regression — PASS

- Live `symbol_info("XAUUSD.")`: 575 symbols, only `XAUUSD.` matches `XAUUSD`/`XAUUSD.`; all 17 fields
  compared programmatically against `evidence/preflight-20261104T174616Z.json` → `DIFFS NONE`, key sets equal.
- `pytest` (JUnit): **88 tests, 0 failures, 0 errors, 0 skipped**, 1.57 s — boundaries 5, config 21,
  logging 6, reporting 4, storage 6, identity 15, investigation 10, service 12, symbols 9.
- AST scan of 12 modules (`src/guardian/**` + `scripts/*.py`): no `order_send` / `order_check` /
  `order_calc_*` / `positions_*` attribute or bare name, and no dict literal with `{action, symbol, volume}`.
- Approval chain recomputed: A-01→A-02→A-03→A-06 all `record_sha256` match and `prev_sha256` link; `A-06` covers D-003 + F1–F4.

## 3. Must fix

None.

## 4. Worth considering

**W1 — release notes still describe the reverted alias as current.**
`CHANGELOG.md:15` says "`RESOLVED` remains as a deprecated alias of `VERIFIED`", while `CHANGELOG.md:23`
in the same 0.2.0 section says the alias was removed, and the runtime has six distinct members.
Impact: a maintainer reading the "Changed" list could restore the alias believing it is intended — that is
exactly the F1 defect. Fix: restate line 15 as "`RESOLVED` is distinct and non-permissive".

**W2 — two account settings are parsed but never enforced.**
`src/guardian/config/settings.py:56,58` (also `configs/config.toml` `expected_company`, `reject_on_mismatch`);
`SymbolResolverService._connection_problem` (`symbol_service.py:57-66`) compares only `trade_mode`, `server`,
`currency`, and the service constructor accepts no company argument.
Impact: the config asserts a company check that does not happen, and `reject_on_mismatch=false` would be
silently ignored (fail-closed, so no bypass). Fix: compare `company` in the gate, or drop both keys from the profile.

## 5. Notes

- `approvals/README.md:20-26` "Current records" table still ends at A-05; `A-06.json` exists and validates.
- End-to-end REAL run records `account_identity PASS` immediately before `account_mode BLOCKED`; correct but contradictory-looking in evidence.
- `scripts/preflight.py:165` hardcodes evidence `"schema_version": 1` while contract `SCHEMA_VERSION` is now 2; pre/post-remediation manifests remain indistinguishable by version.
- Name pinning is config-level: with `aliases` widened *and* `required_symbol_name` removed, bare `XAUUSD` would verify; nothing in code pins the literal.
- `SymbolSpec.visible` / `trade_allowed_by_broker` are not gated by the identity policy (unchanged from before).

## 6. Coverage and what was not verified

**Executed:** live attach/symbol table/metadata via `Mt5ReadOnlyAdapter`; `identify_gold_symbol` for all three
policies on the live table plus synthetic tables; `preflight.main()` four times against a temp `ROOT`
(control PASS, bare-only, REAL, single-winner) and twice more with the policy overridden to each legacy policy;
service probes for REAL/wrong-server/unknown-policy/generic-fault; config loader unknown-policy probe;
full pytest with JUnit; AST order-API scan; approval-chain recomputation.

**Not verified:** no commit was made and no evidence file was written inside the repo. `filling_mode` bit
semantics remain unverified (field reported, never gated). The approval's human origin is asserted by
`A-06.json` but cannot be authenticated by a local hash chain (per `approvals/README.md`).
