# D-003 — XAUUSD Symbol Investigation

- **Date:** 2026-11-04
- **Scope:** read-only investigation. No production code modified, nothing committed, no orders, no account financial fields read.
- **Evidence base:** live `MetaTrader5` metadata read (terminal build 6230, `AronMarkets-Demo`), captured verbatim in `tests/fixtures/gold_candidates_20261104.json`, plus 10 fixture-driven tests (48/48 suite green).
- **Verdict:** investigation **PASS**; the proposed correction is **NOT IMPLEMENTED** (blocked on human approval, per §7 of the task).

---

## 1. The four candidates — actual metadata

| Field | `XAUUSD.` | `XAUEUR.` | `GOLD.` | `GoldmanSachs.` |
|---|---|---|---|---|
| path | `Pure\Spot Metals\Gold\XAUUSD.` | `Pure\Spot Metals\Others\XAUEUR.` | `Pure\Shares\Shares USA\GOLD.` | `Pure\Shares\Shares USA\GoldmanSachs.` |
| description | Gold vs US Dollar / Spot | Gold vs Euro / Spot | Barrick Gold Corp | Goldman Sachs Group |
| currency_base | **USD** | EUR | USD | USD |
| currency_profit | USD | EUR | USD | USD |
| contract size | 100.0 | 100.0 | 100.0 | 100.0 |
| digits / point | 2 / 0.01 | 2 / 0.01 | 2 / 0.01 | 2 / 0.01 |
| tick size / tick value | 0.01 / 1.0000 | 0.01 / 1.1219 | 0.01 / 1.0000 | 0.01 / 1.0000 |
| volume min/step/max | 0.01 / 0.01 / 10.0 | 0.01 / 0.01 / 10.0 | 0.01 / 0.01 / 10.0 | 0.01 / 0.01 / 10.0 |
| trade_mode | 4 (full) | 4 | 4 | 4 |
| execution mode | 2 (market) | 2 | 2 | 2 |
| filling_mode | 1 (FOK) | 1 (FOK) | 1 (FOK) | 1 (FOK) |
| stops level / freeze | **10** / 0 | 20 / 0 | 6 / 0 | 41 / 0 |
| visible / selected | **true / true** | false / false | false / false | false / false |
| trade_calc_mode | **4** | **4** | **2** | **2** |
| swap_mode / long / short | 0 / −72.523 / 22.83 | 1 / −34.87 / 11.68 | 5 / −10.8 / 0.42 | 5 / −10.8 / 0.42 |

Denied cross, for completeness: `XAUXAG.` — `Pure\Spot Metals\XAUXAG.`, "Gold vs Silver", base `XAU`, profit `XAG`, contract 1.0, digits 3, **trade_mode 0 (disabled)**, score 5.

*Rounding note (auditor finding 3/4): `XAUEUR.trade_tick_value` is stored as 1.1219 (live 1.12188 / 1.12177, time-varying FX conversion, unused by the score) and the swap figures above are rounded to 2 dp. Every other field matches the live terminal exactly.*

## 2. Why the four tied — score decomposition

| Weight | `XAUUSD.` | `XAUEUR.` | `GOLD.` | `GoldmanSachs.` | Fires because |
|---|---|---|---|---|---|
| XAU/Gold in path\|description (+2) | 2 | 2 | 2 | 2 | "Gold vs …", "Barrick **Gold** Corp", "**Gold**man Sachs" |
| contract == 100 (+2) | 2 | 2 | 2 | 2 | US share CFDs use 100 units on this broker |
| base == XAU (+3) | **0** | **0** | **0** | **0** | never fires — see R1 |
| digits == 2 (+1) | 1 | 1 | 1 | 1 | shared profile |
| tick == 0.01 (+1) | 1 | 1 | 1 | 1 | shared profile |
| **total** | **6** | **6** | **6** | **6** | margin 0 → `AMBIGUOUS` |

## 3. Root cause — three independent defects in the rule

**R1 — dead weight.** The +3 `currency_base == XAU` weight never applies to the target. On this broker spot metals are quoted with a fiat base: `XAUUSD.` reports `USD/USD`, `XAUEUR.` reports `EUR/EUR`. The maximum attainable score for the intended symbol is therefore **6, not 9**. The only symbol where the weight fires is `XAUXAG.` (`base=XAU`) — a **disabled** cross. So the strongest weight in the design rewards the one symbol that can never be traded.

**R2 — substring false positives.** Matching "XAU or Gold" in `path`/`description` catches an equity issuer ("Barrick Gold Corp") and a bank ("Goldman Sachs Group"). These are not aliases of gold; they are companies whose names contain the word.

**R3 — non-discriminating numeric weights.** `contract_size=100`, `tick_size=0.01`, `digits=2` describe the instrument's *formatting*, not its *identity*. This broker lists US share CFDs with the same 100/0.01/2 profile, so 4 of the 6 points are shared with unrelated instruments.

Aggregate: 2+2+1+1 = 6 for four symbols, margin 0. The acceptance rule then correctly converts the collision into a block — **the gate behaved properly; the score was the defect**. The algorithm is a similarity measure being used as an identity test, and no weighted sum over correlated, non-unique features can guarantee a unique winner.

## 4. What actually identifies `XAUUSD.`

| Discriminator | Unique here? | Stable? | Verdict |
|---|---|---|---|
| **exact name `XAUUSD.`** | yes | broker-configurable, but that *is* the instrument | **primary key** (with configurable alias regex) |
| path class `Spot Metals` | yes among the four | broker taxonomy, machine-readable | **required corroboration** |
| `currency_profit == USD` (account ccy) | no (equities too) | yes | **required corroboration** |
| contract 100 / tick 0.01 / digits 2 | no | yes | sanity check only |
| `visible == true` | yes | **no** — terminal UI state, per-user | never an identity key |
| `trade_calc_mode` 4 vs 2 | yes | undocumented on this bridge; correlation only | do not depend on it |
| `stops_level` 10 / swap_mode | yes | broker risk setting, changes anytime | never |
| description "Gold vs US Dollar / Spot" | yes | human text, locale-dependent | tertiary fallback |

## 5. Answers to the five required questions

1. **Why the same score?** R1+R2+R3: the only weight that could separate the classes is dead, the textual weight fires on company names, and four of six points describe formatting shared with equities.
2. **Which metadata uniquely identifies it?** The exact symbol name `XAUUSD.`; corroborated by the `Spot Metals` path class and `currency_profit == USD`. No numeric property is unique.
3. **Are the others alternatives, aliases, or unrelated?** `XAUEUR.` = same metal, different quote currency (alternative instrument, wrong settlement currency). `XAUXAG.` = gold/silver ratio cross (different instrument, disabled). `GOLD.` = Barrick Gold Corp and `GoldmanSachs.` = Goldman Sachs Group — **unrelated equities**, not aliases.
4. **Is the algorithm defective?** Yes, structurally — not because it produced a tie, but because it attempts identity by similarity. The tie is a symptom; the defect is the absence of a hard identity constraint and of an instrument-class filter.
5. **Safest correction?** Two-stage resolver (below): hard identity first, metadata corroboration second, class-filtered scoring only as fallback. No weakening of the margin rule.

## 6. Recommended correction (proposal P1 — for approval, not implemented)

```
Stage A  identity
         exact match against configurable alias set (default regex ^XAUUSD\.?$, case-insensitive)
         0 match  -> Stage C
         1 match  -> Stage B
         >1 match -> AMBIGUOUS (block)

Stage B  corroboration (fail-closed; report the exact failing field)
         path contains "Spot Metals"
         currency_profit == account currency
         contract_size == 100.0
         tick_size == 0.01
         digits == 2
         trade_mode == 4
         any mismatch -> BLOCKED with the field name and both values

Stage C  fallback (no hardcoded single answer)
         existing weighted score, but only over symbols in "Spot Metals"
         with currency_profit == account currency
         keep min_score 5 and min_margin 2; otherwise BLOCKED
```

Properties: the alias set lives in `configs/config.toml` (versioned, not code) so a broker rename is a config change; stage B never silently accepts a mismatch — it stops and names the inconsistency, exactly as §4 requires; stage C preserves the original algorithm for brokers that name gold differently.

Rejected alternatives: keeping the current rule and raising `min_margin` (makes blocking worse, not better); using `visible` (user state); hardcoding the string `"XAUUSD."` alone without corroboration (breaks on rename, gives no inconsistency report).

## 7. Risks and backward compatibility

| Risk | Mitigation |
|---|---|
| Broker renames gold (`XAUUSDm`, `XAUUSD.r`) | alias regex is configuration; no code change |
| Broker recategorises gold outside `Spot Metals` | stage B blocks and names the field — visible failure, never a silent wrong symbol |
| Gold CFD with contract ≠ 100 elsewhere | blocks with the exact inconsistency (intended behaviour) |
| Behaviour change for current users | new policy name `xauusd_identity_v3`; `xauusd_strict_v1` retained for replay/audit; default stays v1 until approved |
| Scope creep into risk/execution | none — resolver signature and `SymbolSpec` unchanged; no risk module touched |

## 8. Tests delivered now (read-only, passing)

`tests/unit/test_symbol_investigation.py` — 10 tests, fixture `tests/fixtures/gold_candidates_20261104.json` (verbatim broker values):
tie reproduction · equities indistinguishable under the rule · base-XAU weight only on the disabled cross · spot-metal class exclusion · visibility not used as identity · duplicate identity match blocks · empty table · wrong-candidate constraint divergence (`stops_level` 10 vs 20 vs 41, `XAUEUR.` settles in EUR) · metadata completeness · target metadata.

**Tests required before P1 ships:** alias variants (`XAUUSD`, `XAUUSD.`, `XAUUSDm`) resolved by config; two identity matches → `AMBIGUOUS`; name match + metadata mismatch → `BLOCKED` naming the field; fallback scoring with class filter on a table without `XAUUSD.`; determinism replay over the captured fixture (hash-stable).

## 9. Remaining unknowns

- U7: whether other Aron servers (real/live naming, other bridges) expose gold under different names — only `AronMarkets-Demo` was inspected.
- U8: stability of the `Spot Metals\Gold` path across broker server upgrades.
- U9: documented meaning of `trade_calc_mode` 4 vs 2 on this bridge — observed correlation, not a published contract.
- U10: why this broker assigns `contract_size=100` to US share CFDs (broker-wide default or per-symbol setting).
- U11: symbol table completeness — 575 symbols visible to the API; hidden/session-gated instruments may exist.

## 10. Independent review (auditor agent, read-only, 2026-11-04)

Full record: `reports/AUDIT-D-003.md`. The auditor re-attached to MT5 read-only, loaded the **full 575-symbol table**, diffed every fixture field, re-ran the suite, and did not edit code.

| Claim | Verdict |
|---|---|
| Four candidates actually inspected | PASS |
| Fixture matches MT5 | PASS (one 8e-6 rounding, unused field) |
| Root cause evidenced | PASS — tie reproduces on the whole live table, not just the fixture |
| Correction does not weaken safety | PASS |
| Tests cover ambiguous/invalid cases | PASS — 10 tests, none skipped |

Auditor additions that strengthen the root cause: `currency_base == XAU` appears on **exactly one** symbol in 575 (`XAUXAG.`, disabled); `AronGold.` and `AronGOLD17W_Mesghal.` score only 2; Stage-C fallback on this broker peaks at 4 (`XPTUSD.`), so it would block rather than guess if `XAUUSD.` disappeared.

### Defects found by the auditor (pre-existing, **not fixed** — production code is frozen in this phase)

| # | Location | Severity | Issue | Proposed correction |
|---|---|---|---|---|
| 1 | `src/guardian/contracts/schemas.py:109` + `scripts/preflight.py:110` | worth considering | `ranked` is annotated `tuple[tuple[str, int], ...]` but produced as `(score, name)`; `preflight.py` follows the annotation, so the BLOCKED evidence line renders `top=6:XAUUSD.` — name and score swapped | annotate `tuple[tuple[int, str], ...]` (or introduce a `RankedSymbol` record) and assert the rendered text |
| 2 | D-003 §6 Stage C | worth considering | fallback filter omits `trade_mode == 4`, unlike Stage B; no current impact (pool peak 4 < 5) | add `trade_mode == 4` to the Stage C filter |

Finding 1 means the tie shown in `evidence/preflight-*.json` is correct in substance but mislabelled in presentation; tests unpack `(score, name)` and therefore encode the true order.

## 11. Status

**Investigation: PASS** — four candidates inspected live, metadata matches, root cause reproduced by fixture test, correction proposed without weakening any check, independently verified.

**Implementation: NOT STARTED** — deliberately, pending explicit approval of D-003 / P1. Nothing was committed; the working tree holds uncommitted report + test files by design.
