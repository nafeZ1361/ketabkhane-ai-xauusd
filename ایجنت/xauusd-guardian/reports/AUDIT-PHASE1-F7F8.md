# AUDIT — PHASE 1, F7/F8 final review

Reviewer pass: 2026-11-04 (local +03:30). Target: F7 (blank `expected_company` silently
disables the account gate) and F8 (no test covered the preflight wiring). Read-only audit:
no file under `src/`, `scripts/`, `configs/`, `tests/` was modified by this pass.

## 1. Conclusion

All seven checks PASS. F7 and F8 are closed; no must-fix finding remains; three
worth-considering items are recorded (none blocks closure). PHASE 1 can be accepted.

| # | Check | Result | Executed evidence |
|---|-------|--------|-------------------|
| 1 | Inspect changed code line by line | PASS | Full read of `symbol_service.py`, `settings.py`, `preflight.py`, `test_symbol_service.py`, `test_config.py`; delta scope bounded by mtimes (check 6) |
| 2 | F7: blank company cannot disable the gate | PASS | 4 probes through `parse_settings` + `build_resolver_service` (below) |
| 3 | F8: preflight wiring covered + mutation | PASS | `-k build_resolver_service` 2 passed; `-k blank` 1 passed; in-memory mutation makes the wiring test fail |
| 4 | Full suite | PASS | `93 passed in 1.46s`, exit 0 |
| 5 | Safety boundary unchanged | PASS | AST scan src+scripts; `test_boundaries.py` 5 passed; three-policy gate probe |
| 6 | Tree + evidence integrity | PASS | mtime delta = declared files; `checks_sha256` recomputed and matched |
| 7 | Acceptance | PASS | no blocker |

### Check 1 — code inspection

`build_resolver_service` (`src/guardian/application/symbol_service.py:128-159`) maps all
nine profile fields (`schema_version`, `aliases`, `required_symbol_name`,
`required_path_token`, `required_profit_currency`, `contract_size`, `tick_size`, `digits`,
`require_full_trade_mode`) into `GoldExpectations`; nothing is dropped. `expected_company`
is passed at line 157 and is the only production call site of `SymbolResolverService(...)`
(grep over `src/` + `scripts/`: one construction site, inside that function).

`settings.py:238-240` rejects blank `expected_server`, `expected_company`, `currency`
before any consumer sees them. `_require_true` (`settings.py:120`) pins
`reject_on_mismatch`. `scripts/preflight.py:90` builds the service only through
`build_resolver_service`; the former local `_expectations` shim is gone (no
`GoldExpectations(` in `preflight.py`).

### Check 2 — F7 proof (real path: TOML -> parse_settings -> build_resolver_service -> resolve)

Adapter identity: `company="Aron Markets Ltd"`, `trade_mode=DEMO`,
`server=AronMarkets-Demo`, `currency=USD`.

```
''               -> ConfigError: [account].expected_company must not be empty; a blank value disables a gate
'   '            -> ConfigError: [account].expected_company must not be empty; a blank value disables a gate
'Other Broker'   -> account_gate_failed=True | CONNECTION_FAILED | company is 'Aron Markets Ltd', expected 'Other Broker'
'Aron Markets Ltd' -> settings ok, gate passed, reached symbol stage (NOT_FOUND with empty specs)
```

Both blank forms are rejected at load time, so they never reach the service; a wrong
non-blank company reaches the service and fails closed. `symbol_service.py:62` compares
whenever `expected_company is not None`, and `build_resolver_service` always supplies a
`str` (the loader cannot produce `None`). The pre-fix behaviour (blank -> `VERIFIED`) is
not reproducible through any config path.

### Check 3 — F8 proof

`pytest tests/unit/test_symbol_service.py -k build_resolver_service -q` -> 2 passed.
`pytest -k blank -q` -> 1 passed.

Mutation (in memory only, no file edits): a subclass of `SymbolResolverService` that pops
`expected_company` from kwargs, installed as
`guardian.application.symbol_service.SymbolResolverService`, then
`test_build_resolver_service_wires_the_account_gate` run:

```
AssertionError: assert False is True
 +  where False = ResolutionOutcome(status=VERIFIED, identity={... 'company': 'Other Broker' ...},
                                   account_gate_failed=False).account_gate_failed
1 failed, PYTEST_RC = 1
```

The mutation reproduces exactly the F7 failure mode, and the test catches it. Residual:
see W1 — the test covers `build_resolver_service`, not `scripts/preflight.py` itself.

### Check 4 — full suite

`.venv\\Scripts\\python.exe -m pytest --tb=short` -> `93 passed in 1.46s`, exit 0.
Per module: boundaries 5, config 23, logging 6, reporting 4, storage 6, identity 15,
investigation 10, service 15, symbols 9. Delta vs the closing audit's 90 is +1 config,
+2 service — matching the two new wiring tests plus one blank-config test.
`evidence/pytest-20261104T192237Z.txt` states 93 passed; count matches (its 3.45 s is a
different machine load, not a discrepancy in the claim being checked).

### Check 5 — safety boundary

- AST over `src/` and `scripts/`: no `order_send`, `order_check`, `order_calc_*`,
  `positions_*`, `orders_get`, `history_*`; the only sensitive attribute is
  `account_info` at `mt5_readonly.py:138`, whose return maps to trade_mode/server/company/
  currency/leverage only.
- `MetaTrader5` appears only in `adapters/mt5_readonly.py` (via `importlib.import_module`);
  `tests/security/test_boundaries.py` -> 5 passed, including the import-confinement and
  sensitive-field tests.
- Gate semantics on the captured broker table: `xauusd_identity_v3` VERIFIED ok=True;
  `xauusd_strict_v1` AMBIGUOUS ok=False; `spot_metal_usd_v2` RESOLVED ok=False;
  `SymbolResolution.ok` is true only for VERIFIED; `VERIFIED is not RESOLVED` -> True.

### Check 6 — tree and evidence integrity

`git status` cannot express "since the last audit" (HEAD is 82ab8b5, predating Phase 1;
`src/guardian/application/` is untracked as a whole), so the delta was bounded by mtimes
against the previous report (21:42 local). Files changed after it:

```
21:43:04  src/guardian/application/symbol_service.py
21:43:04  src/guardian/config/settings.py
21:43:22  scripts/preflight.py
21:43:22  tests/unit/test_config.py
21:43:22  tests/unit/test_symbol_service.py
21:44:10  CHANGELOG.md, DECISIONS_LOG.md, PROJECT_STATE.md
```

Exactly the declared delta; no stray edit to source, tests or config. No source/test file
was modified after the evidence run (newest source 18:13 UTC, evidence 19:22 UTC).

`checks_sha256` recomputation over the `checks` array of
`evidence/preflight-20261104T192250Z.json`:

```
stored : sha256:8bcc116f78625c214952ebf5ba8a4833c938a91f98e9fe95426f85ac00303676
recalc : sha256:8bcc116f78625c214952ebf5ba8a4833c938a91f98e9fe95426f85ac00303676
MATCH  : True   (9 checks, exit_code 0)
```

## 2. Must fix

None.

## 3. Worth considering

**W1 — `scripts/preflight.py` is still not exercised by any test.** `preflight.py:90`
calls `build_resolver_service`, but no test file references `preflight` (search over
`tests/`: 0 hits). Deleting that call and constructing the service directly would leave
all 93 tests green, so the F8 failure mode can return through the script even though the
function it currently calls is covered. Impact: a future refactor of the entry point is
unprotected; today's runtime is correct. Fix: one test that imports `scripts.preflight`
with a fake adapter/settings and asserts exit 2 plus `account_mode BLOCKED` on a company
mismatch — or an architecture test forbidding `SymbolResolverService(...)` outside
`guardian.application`.

**W2 — the permissive value is the constructor default.** `symbol_service.py:38`:
`expected_company: str | None = None`. Unreachable from config today (the loader rejects
blanks and always yields a `str`), but a second construction site added later would skip
the company gate by omission, silently. Fix: make it a required keyword argument, or
assert non-`None` inside `build_resolver_service`.

**W3 — docs overstate the coverage.** `CHANGELOG.md:28` and `PROJECT_STATE.md:73` describe
the two new tests as "end-to-end". Both use `FakeAdapter` and never import
`scripts/preflight.py` or touch a terminal; they cover config -> service, not the gate
script. Impact: the next reader will believe the preflight path itself is exercised.
Fix: describe them as config->service wiring tests.

## 4. Notes

- `preflight.py` still writes evidence `"schema_version": 1` while `contracts.SCHEMA_VERSION`
  is 2 — carried over from earlier passes, untouched by this delta.
- An account-gate mismatch is carried as `symbol.status = CONNECTION_FAILED`
  (`symbol_service.py:69-76`), so the manifest's `symbol` block reads "connection failed"
  while `checks[]` correctly records `account_mode BLOCKED`. Read `checks[]` first.
- The blank-field loop covers three keys (`settings.py:238`) but
  `test_config.py:149` exercises only `expected_company`; the other two are covered by the
  same loop, not by a test.
- `evidence/preflight-20261104T181349Z.json` is an untracked intermediate run from the fix
  session; it is stale relative to the accepted evidence pair and claims nothing.
- Evidence pytest duration (3.45 s) vs current run (1.46 s): timing only; the 93 count is
  identical.

## 5. Scope and what was not covered

**Executed:** full read of the three production modules, both changed test modules, the
config and the three docs; four loader/service probes for blank and wrong company; one
in-memory mutation run of the wiring test; two targeted pytest selections; the full suite;
AST scans of `src/` and `scripts/` for order APIs and MT5 imports; the five boundary tests;
a three-policy gate probe on the captured broker table; SHA-256 recomputation of the
preflight manifest; mtime-based scope diff against the previous audit.

**Not covered:** a live `preflight.main()` re-run (it attaches to the running terminal and
writes a new evidence file; this pass is read-only) — the accepted manifest was therefore
verified for integrity and internal consistency, not re-generated. No commit baseline
exists, so "delta" rests on mtimes rather than `git diff`. `scripts/preflight.py` was read
and reasoned about but not executed.
