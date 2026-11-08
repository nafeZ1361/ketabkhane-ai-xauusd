# AUDIT-PHASE1-D003 — Phase 1 symbol-resolution audit

**Auditor:** independent reviewer (read-only). **Date:** 2026-11-04.
**Tree:** `master` @ `82ab8b5` + uncommitted working tree; 10 modified, 6 new `.py` files.
**Environment:** `.venv` Python 3.11.8; MetaTrader5 5.0.6231; terminal build 6230; account DEMO.
**Baseline:** the eight numbered points in the task brief; project rules forbidding orders and balance/equity reads; `DECISIONS_LOG.md` D-003/D-009.

## Verdict

Not ready to accept: **2 must-fix**. Both concern the single guarantee the gate exists to provide — that only a metadata-corroborated `XAUUSD.` can produce `PASS`. The live metadata, the four mismatch paths, the connection/ambiguity paths, the absence of order code, the suite (81 passed) and the ranking fix all hold.

## 1. Point-by-point

| # | Verdict | Evidence |
|---|---|---|
| 1 | PASS | All 10 modified and 6 new `.py` files read in full, plus the 3 modified docs. `git status` also lists `CHANGELOG.md`, `DECISIONS_LOG.md`, `PROJECT_STATE.md`, absent from the brief's list. |
| 2 | PASS | Live `symbol_info("XAUUSD.")` equals the evidence manifest field-for-field (§1.1). Re-resolved through the real adapter/service: `VERIFIED`, identical `observed`. Evidence `checks_sha256` recomputes to the stored value. |
| 3 | **FAIL** | Today's pick is `XAUUSD.`, but the guarantee is not enforced: bare `XAUUSD` also verifies (F2), and the still-selectable `spot_metal_usd_v2` returns `VERIFIED` with no metadata check (F1). |
| 4 | PASS | Alias absent → `NOT_FOUND`; `contract_size=10` → `METADATA_MISMATCH(('contract_size','100','10'),)`; path `Pure\Forex\...` → mismatch `path`; `trade_mode=3` → mismatch `trade_mode`. Output in §1.2. |
| 5 | PASS | `attach()` raising → `CONNECTION_FAILED`, `fingerprint=None`; duplicate alias → `AMBIGUOUS` (domain and service); REAL account → `CONNECTION_FAILED`. |
| 6 | PASS | AST scan of the 12 changed/new modules and all of `src/guardian` + `scripts/` (2 files): zero `order_send` / `order_check` / `order_calc_*` calls, zero dict literals shaped like a trade request. |
| 7 | PASS | `.\.venv\Scripts\python.exe -m pytest` → `81 passed in 2.51s`, exit 0, no skips. Counts per file in §5. |
| 8 | PASS | Producers emit `(score, name)` (`symbols.py:144`, `:267`); `format_ranked` unpacks `for score, name` and prints `name:score`; probe → `GOLD.:6, XAUXAG.:5, AronGold.:2`; `preflight.py:139` is the only renderer. |

### 1.1 Live metadata vs evidence (point 2)

Raw `MetaTrader5.symbol_info("XAUUSD.")`, read-only, terminal build 6230.

| Field | Live | Evidence `observed` | Config expectation | Verdict |
|---|---|---|---|---|
| name | `XAUUSD.` | `XAUUSD.` | alias list | ok |
| path | `Pure\Spot Metals\Gold\XAUUSD.` | same | contains `Spot Metals` | ok |
| description | `Gold vs US Dollar / Spot` | same | not gated | ok |
| currency_base | `USD` | `USD` | not gated | ok |
| currency_profit | `USD` | `USD` | `USD` | ok |
| contract_size | `100.0` | `"100"` | `100.0` | ok |
| digits | `2` | `"2"` | `2` | ok |
| point | `0.01` | `"0.01"` | not gated | ok |
| tick_size | `0.01` | `"0.01"` | `0.01` | ok |
| tick_value | `1.0` | `"1"` | not gated | ok |
| volume_min | `0.01` | `"0.01"` | not gated | ok |
| volume_max | `10.0` | `"10"` | not gated | ok |
| volume_step | `0.01` | `"0.01"` | not gated | ok |
| trade_mode | `4` (FULL) | `"4"` | `4` | ok |
| stops_level | `10` | `"10"` | not gated | ok |
| freeze_level | `0` | `"0"` | not gated | ok |
| filling_mode | `1` (bitmask) | `"1"` | not gated | ok |

`symbols_get()` contains `XAUUSD.` and `XAUUSDT.`, no bare `XAUUSD`; 575 symbols in total.

### 1.2 Probe output (points 4, 5, 8)

```
A_ALIAS_ABSENT: status=NOT_FOUND ok=False name=None
B_CONTRACT_SIZE: status=METADATA_MISMATCH name=XAUUSD. mism=(('contract_size', '100', '10'),)
C_PATH_CLASS: status=METADATA_MISMATCH name=XAUUSD. mism=(('path', "contains 'Spot Metals'", 'Pure\\Forex\\XAUUSD.'),)
D_TRADE_MODE_CLOSED: status=METADATA_MISMATCH name=XAUUSD. mism=(('trade_mode', '4', '3'),)
E_DUPLICATE_ALIAS: status=AMBIGUOUS name=None
F_BARE_XAUUSD_ONLY: status=VERIFIED name=XAUUSD
H_ATTACH_RAISES: status=CONNECTION_FAILED fp=None | terminal attach failed: IPC timeout
I_SERVICE_DUPLICATE: status=AMBIGUOUS
J_REAL_ACCOUNT: status=CONNECTION_FAILED | account trade_mode is 'REAL', expected 'DEMO'
RANK_FMT GOLD.:6, XAUXAG.:5, AronGold.:2
```

## 2. Must fix

### F1 — legacy scoring policies return `VERIFIED` and can open the gate

**Location:** `src/guardian/contracts/schemas.py:54` (with `:139`), `src/guardian/domain/symbols.py:289`, `scripts/preflight.py:30-33`.

**Problem:** `RESOLVED = "VERIFIED"` is an enum *alias*, not a distinct member, so `ResolutionStatus.RESOLVED is ResolutionStatus.VERIFIED` is `True`. `SymbolResolution.ok` only tests `is VERIFIED`, therefore every legacy branch that returns `RESOLVED` is permissive. `STATUS_LABEL` then maps it to `PASS/0`.

**Evidence (live symbol table, this terminal):**

```
xauusd_strict_v1    -> AMBIGUOUS ok False  (4-way tie at 6)
spot_metal_usd_v2   -> VERIFIED  ok True   name XAUUSD. margin None
```

`configs/config.toml:8` advertises both as selectable and `settings.py:23` accepts them. Setting `symbol_policy = "spot_metal_usd_v2"` produces `PASS symbol_resolution = VERIFIED`, exit 0, with `symbol.observed = {}` and `mismatches = []` — no path/currency/digit/tick corroboration was performed, yet the artifact attests `VERIFIED`. Synthetic single-winner case with `xauusd_strict_v1` yields `VERIFIED` for `XAUUSD.m` (probe `G`, label `('PASS', 0)`).

**Impact:** the gate's central claim becomes false and is persisted as evidence. An operator reading `symbol.status = VERIFIED` cannot tell a corroborated identity from a score winner. `tests/unit/test_symbols.py:55` also still passes while asserting `RESOLVED`, now silently meaning `VERIFIED`.

**Basis:** `schemas.py:46` "Only `VERIFIED` is permissive"; `DECISIONS_LOG.md:22` "the resolver never falls back to another symbol"; brief point 3.

**Correction:** give `RESOLVED` its own non-permissive value (or delete it and update the legacy return), and make `preflight` refuse `PASS` unless `resolution.policy == "xauusd_identity_v3"` — defense in depth for the next policy added.

### F2 — the resolver accepts a symbol that is not `XAUUSD.`

**Location:** `configs/config.toml:23`; `src/guardian/domain/symbols.py:103` (default) and `:133` (match).

**Problem:** `aliases = ["XAUUSD", "XAUUSD."]`. Identity is satisfied by either, so the resolver returns `VERIFIED` for bare `XAUUSD`, a different instrument.

**Evidence:** probe `F_BARE_XAUUSD_ONLY` → `status=VERIFIED name=XAUUSD`. Not triggered today: the live table has no bare `XAUUSD`, and if both names existed the resolver correctly returns `AMBIGUOUS` (probe `E`).

**Impact:** after a broker rename or suffix change (or on a second broker) the gate passes on `XAUUSD` with no operator-visible difference; the brief's "exactly `XAUUSD.`" requirement is not enforced in code. Contradicts `DECISIONS_LOG.md:22-23`.

**Correction:** pin the production alias list to `["XAUUSD."]`, or add a `required_symbol_name` to `GoldExpectations` that the returned `symbol_name` must equal. Case-insensitivity can stay.

## 3. Worth considering

**F3 — account refusal is reported as a symbol/connection failure.**
`scripts/preflight.py:128-142`, `src/guardian/application/symbol_service.py:48-60`. Server/currency/trade-mode mismatch returns `CONNECTION_FAILED`, so the gate records `symbol_resolution = FAIL` while `account_identity` is `PASS`; a REAL account also records `account_mode BLOCKED` but exits **1**, not 2, where the previous code returned 2. Impact: exit-code consumers read a prohibited account type as a connection fault, and the failing check name points at the resolver. Suggest a separate `account_identity` gate with `BLOCKED/2`, or rename the recorded check.

**F4 — duplicated policy registry.**
`src/guardian/config/settings.py:23` vs `src/guardian/domain/symbols.py:36`. If the lists drift, the loader accepts a policy the domain rejects; `identify_gold_symbol` raises `ValueError`, and the service's broad `except Exception` converts it to `CONNECTION_FAILED` "terminal read failed". Impact: a config/programming error is diagnosed as a terminal problem. Suggest one source of truth and not catching `ValueError` as a connection fault.

**F5 — D-003 acceptance has no approval record.**
`DECISIONS_LOG.md:20` says D-003 is "ACCEPTED AND IMPLEMENTED (2026-11-04, Phase 1 authorization)"; `approvals/` holds only A-01…A-03, and `approvals/README.md` says "Never infer an approval from … an agent's own statement". Impact: the default-policy change and the newly open gate rest on an authorization not recorded in the repo. I cannot see chat history, so this is unverified rather than false. Suggest recording the approval (e.g. A-06) or citing where it lives.

## 4. Notes

- `CHANGELOG.md:11` says "33 new tests"; the suite grew 38 → 81 (43); the 10 `test_symbol_investigation.py` tests are not counted. Documentation arithmetic only.
- `src/guardian/domain/symbols.py:117` `_EXECUTION_MODES_NOTE` is assigned and never used.
- `scripts/preflight.py:166` writes `"ranked": ""` (string) when empty while the rest of `symbol` is structured; consumers need a special case.
- `SymbolResolution` gained members and fields but `SCHEMA_VERSION` stayed 1 (`schemas.py:17`); old and new evidence cannot be version-distinguished.
- The brief's changed-file list omits the three modified docs; all three are in the tree.

## 5. Coverage and what was not verified

**Read in full:** the 10 modified `.py`/config files, the 6 new modules and tests, the fixture, the doc diffs, `approvals/README.md` and `A-03.json`.

**Executed:**
- `git status --porcelain`, `git diff --stat`, full `git diff`, `git ls-files --others`.
- Live `MetaTrader5.symbol_info("XAUUSD.")` and `symbols_get()`; live `SymbolResolverService.resolve()` through `Mt5ReadOnlyAdapter` (attach → read → detach); no order calls.
- `%TEMP%\audit_d003_probe.py`: four mismatch paths, duplicate alias, bare-alias-only, legacy winners, attach failure, REAL account, `STATUS_LABEL`, `format_ranked`.
- Full `pytest` twice (exit 0), `pytest --collect-only` per file: boundaries 5, config 19, logging 6, reporting 4, storage 6, identity 13, investigation 10, service 10, symbols 8 = 81.
- AST order-API scan over changed/new modules, all of `src/guardian`, `scripts/`.
- Recompute of the evidence `checks_sha256` → matches.

**Not verified:**
- `scripts/preflight.py` end-to-end: `main()` writes a new `evidence/` file, which the brief forbids; the same resolution path was exercised live through the service. Exit-code mapping was read from the imported module (`STATUS_LABEL`), which has no side effects.
- `filling_mode` bit semantics: the local package exports no `SYMBOL_FILLING_*`; raw value `1` matches live and the field is reported, never gated (`symbols.py:117`).
- Whether D-003's "Phase 1 authorization" exists outside the repo.
- Balance/equity/margin/profit were not read; `account_identity()` supplied only trade_mode/server/company/currency/leverage.