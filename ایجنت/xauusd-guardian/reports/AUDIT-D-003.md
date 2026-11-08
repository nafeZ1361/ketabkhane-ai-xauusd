# AUDIT-D-003 - independent re-verification

- Auditor: reviewer agent (read-only), 2026-11-04.
- Baseline: the five claims in the audit brief; project rules (no orders, no account financial fields, no code edits, no commits).
- Method: read D-003, fixture, tests, `symbols.py`, `schemas.py`; live read-only MT5 attach via `.venv` MetaTrader5 (build 6230, approved path); full 575-symbol table loaded in memory; `pytest -q` run.

## Verdict per claim

| # | Claim | Verdict |
|---|---|---|
| 1 | Four candidates actually inspected | PASS |
| 2 | Fixture matches MT5 exactly | PASS (one 8e-6 rounding, unused field) |
| 3 | Root cause evidenced (`base==XAU` dead, shared 100/0.01/2, 6+6+6+6) | PASS |
| 4 | Proposed A/B/C does not weaken safety | PASS |
| 5 | Tests cover tie, duplicates, empty, divergence | PASS |

Test suite: 48 collected, 48 passed, exit 0 (5 security, 13 config, 6 logging, 6 storage, 10 symbol_investigation, 8 symbols).

## Evidence

### E1 - live metadata (read-only)

`mt5.initialize(path=...)` -> True, build 6230. Only `symbol_info`, `symbols_get`, `symbols_total` called; no `account_info`, no orders, no balance/equity.

| name | path | base/profit | contract | digits | tick | mode | stops | visible |
|---|---|---|---|---|---|---|---|---|
| XAUUSD. | Pure\Spot Metals\Gold\XAUUSD. | USD/USD | 100.0 | 2 | 0.01 | 4 | 10 | True |
| XAUEUR. | Pure\Spot Metals\Others\XAUEUR. | EUR/EUR | 100.0 | 2 | 0.01 | 4 | 20 | False |
| GOLD. | Pure\Shares\Shares USA\GOLD. | USD/USD | 100.0 | 2 | 0.01 | 4 | 6 | False |
| GoldmanSachs. | Pure\Shares\Shares USA\GoldmanSachs. | USD/USD | 100.0 | 2 | 0.01 | 4 | 41 | False |
| XAUXAG. | Pure\Spot Metals\XAUXAG. | XAU/XAG | 1.0 | 3 | 0.001 | 0 | 0 | False |

All five exist; none invented.

### E2 - field-by-field fixture diff

Every fixture key compared for all 5 symbols (float tolerance 1e-9). **1 mismatch**: `XAUEUR.trade_tick_value` = 1.1219 in fixture vs 1.12188 live (later re-read 1.12177 - the field is time-varying FX conversion). Not used by scoring. Fixture note says "verbatim"; this one value is 4-dp rounded.

### E3 - full 575-symbol table

`mt5.symbols_total()` = 575, `symbols_get()` returned 575. Built `SymbolSpec` for all, ran `identify_gold_symbol(..., STRICT_POLICY)`:

- status AMBIGUOUS, margin 0, reason: "4 symbols tie at score 6 ... GOLD., GoldmanSachs., XAUEUR., XAUUSD."
- ranked: (6, GOLD.), (6, GoldmanSachs.), (6, XAUEUR.), (6, XAUUSD.), (5, XAUXAG.)

Extra symbols checked because their names contain GOLD: `AronGold.` score 2 (contract 1000, digits 0, tick 100, mode 3), `AronGOLD17W_Mesghal.` score 2 (contract 230.85, digits 0, tick 500, mode 3). `XAUUSDT.` (Crypto Majors) exists but does not score into the tie. So the four-way tie is not an artefact of a truncated fixture: it reproduces exactly on the whole live table.

`currency_base == XAU` across all 575: only `XAUXAG.` (trade_mode 0). The report's R1 holds broker-wide, not just for the fixture.

`AMENDED_POLICY` on the full table: RESOLVED `XAUUSD.`, margin None (sole eligible symbol).

Stage C simulation (path contains "Spot Metals" AND currency_profit USD): XAUUSD. 6, XPTUSD. 4, XPDUSD. 2, XAGUSD. 0. If XAUUSD. were absent the best score 4 < min_score 5 -> NOT_FOUND. Fallback would block on this broker.

### E4 - required test cases

| Case | Test | Line | Result |
|---|---|---|---|
| 4-way tie | `test_four_way_tie_is_reproducible` | 82 | pass |
| duplicate identity | `test_two_identity_matches_block_instead_of_guessing` | 124 | pass |
| empty table | `test_empty_table_is_not_found` | 134 | pass |
| wrong-candidate divergence | `test_choosing_the_wrong_candidate_changes_broker_constraints` | 139 | pass |

10 tests in the file; none skipped/xfailed.

### E5 - correction safety checklist (D-003 section 6)

- Blocks on ambiguity: Stage A `>1` match -> AMBIGUOUS; Stage C keeps margin 2. PASS.
- No dependence on `visible`: not referenced in A/B/C; `test_visibility_is_not_used_as_identity` (line 116) passes with an invisible XAUUSD. PASS.
- No uncorroborated hardcoded symbol: alias regex is configurable, Stage B re-checks six broker fields. PASS.
- Fallback keeps min_score 5 / min_margin 2: stated in section 6; module constants `symbols.py:30-31` are 5/2. PASS.
- Stage B fail-closed: any mismatch -> BLOCKED naming the field. PASS (design text).

## Findings

1. `src/guardian/contracts/schemas.py:109` + `scripts/preflight.py:110` | **worth considering** | `ranked` is annotated `tuple[tuple[str, int], ...]` but produced as `(score, name)` (`symbols.py:101-103`). `preflight.py:110` follows the annotation (`for name, score in ...`) and therefore renders `top=6:XAUUSD.` - score and name swapped - in the BLOCKED line that is supposed to evidence the tie. Tests unpack `(score, name)`, so they encode the real order. Pre-existing, not introduced by D-003. Correction: annotate `tuple[tuple[int, str], ...]`, or emit a small `RankedSymbol` record and update preflight; add one assertion on rendered text.
2. D-003 section 6, Stage C | **worth considering** | Fallback filter is path `Spot Metals` + `currency_profit == account currency`, but unlike Stage B it does not require `trade_mode == 4`. A disabled symbol scoring >=5 in that class would be resolved. No current impact: live pool peaks at 4 (XPTUSD.), so min_score 5 blocks. Correction: add `trade_mode == 4` to the Stage C filter for parity with Stage B; no behaviour change on the captured table.
3. `tests/fixtures/gold_candidates_20261104.json:43` | **record only** | `trade_tick_value` 1.1219 vs live 1.12188/1.12177; rounded, dynamic, unused by the score.
4. D-003 section 1 table | **record only** | swap figures are rounded (`XAUEUR.` -34.87/11.68 vs live -34.8706/11.6835). Immaterial.
5. D-003 section 1 / section 10 | **record only** | server `AronMarkets-Demo` and capture time 16:52Z could not be re-verified: `account_info` is prohibited by the task, so only build 6230 was confirmed.
6. Design note | **record only** | Stage A narrows candidates before corroboration, so a same-metal variant outside the alias list (e.g. `XAUUSDm`) is never compared with the exact match. Live table has only `XAUUSD.` (Spot Metals) and `XAUUSDT.` (Crypto), so no current exposure; the alias test listed in D-003 section 8 should cover it.

## Not covered

- Server identity and capture timestamp (see finding 5).
- Other brokers/servers; D-003 U7-U11 remain open and correctly labelled unknown.
- No production file was edited; no commit; no order or account-financial call was made.
