# PROJECT_STATE

Last updated: 2026-11-08 (Phase 3 / W1)

## Phase status

| Phase | Status | Note |
|---|---|---|
| 0 Reconnaissance | DONE | 2026-11-03, `READY_WITH_BLOCKERS` |
| 0.5 Reconciliation | DONE | `PHASE_0_5_RESOLUTION.md` (workspace root), 4 blockers mapped |
| 1 Foundation | **PASS** (provisional, awaiting human sign-off) | structure, config, contracts, logging, storage, migrations, tests, identity resolver; three independent audit passes, no must-fix open |
| 2 Market data | **ACCEPTED** | Phase 2 accepted under A-08 (2026-11-05); see `reports/PHASE2-REMEDIATION-REPORT.md` and approval chain A-01→A-08 |
| 3 Analysis/strategy | **IN PROGRESS** | S1–S4 PASS; W1 timezone validation PASS (independent Inspector; 220/220 tests on `fix/w1-timezone-validation`); S1–S5 PASS (252/252 tests, S5 committed as 9a3b53a); S6 implemented (migration reversal) pending independent sign-off; S7 open |
| 4 Risk | NOT STARTED | |
| 5 Firewall | NOT STARTED | |
| 6 Backtest | NOT STARTED | |
| 7 Monitoring | NOT STARTED | |
| 8 Integration | NOT STARTED | |
| 9 Independent audit | NOT STARTED | |
| 10 Remediation | NOT STARTED | |
| 11 DEMO readiness | NOT STARTED | order submission not authorized |

## Approvals held

- A-01 workspace creation — APPROVED (2026-11-04)
- A-02 venv + pinned dependencies — APPROVED (2026-11-04)
- A-03 local git repository — APPROVED (2026-11-04)
- A-06 implement D-003 identity resolver + reporting fixes — APPROVED (2026-11-04, `approvals/A-06.json`)
- A-07 Phase 2 implementation — **SUPERSEDED BY A-08 as evidence**; retained unchanged as history
- A-08 Phase 2 scope confirmation and acceptance — **GRANTED** (2026-11-05, `approvals/A-08.json`, `record_sha256=d7126270…`)

## Open approvals

- (none for Phase 2 — A-08 granted; A-04/A-05 below remain closed)- A-04 balance/equity access — NOT REQUESTED (synthetic fixtures only)
- A-05 DEMO-level order checks / DEMO execution — NOT REQUESTED
- D-003 symbol policy amendment `spot_metal_usd_v2` — **PENDING**

## Blockers

| ID | State |
|---|---|
| B1 isolated venv | RESOLVED (A-02) |
| B2 gold symbol resolution | **RESOLVED** — policy `xauusd_identity_v3` returns `VERIFIED` on `XAUUSD.` (preflight 2026-11-04 17:24Z) |
| B3 terminal path / APPDATA | RESOLVED (explicit `path=`, verified path match, works with APPDATA absent) |
| B4 FOK + stop distance | PARTIAL (filling_mode=1 FOK, stops_level=10 confirmed live; `order_check` needs A-05) |

## Phase 1 evidence (2026-11-04)

| Item | Result |
|---|---|
| Tests | `93 passed`, exit 0 — `evidence/pytest-20261104T192237Z.txt` |
| Preflight | `verdict: PASS`, exit 0 — `evidence/preflight-20261104T192250Z.json` (9 checks, `checks_sha256` recomputed and matched) |
| Symbol | `VERIFIED XAUUSD.` — exact identity corroborated by six metadata fields |
| Spread sample | `[16, 16, 16]` points — varies 10 → 20 → 19 → 18 → 19 → 16 within one day: U5 confirmed |
| Interpreter | `.venv` → 3.11.8, `MT5 5.0.6231`, `pytest 9.2.0` |

### Earlier gate run (v1, superseded)

`verdict: BLOCKED`, exit 2 — the strict policy correctly refused to choose between four symbols tied at score 6. Kept as `evidence/preflight-20261104T163752Z.json`: it is the proof that the gate blocks rather than guesses.

### Defects found during Phase 1 and corrected

1. `preflight.py` imported `MetaTrader5` directly — caught by the AST boundary test.
2. Boundary test used a substring check and a `Path`/`str` comparison bug — replaced with a precise AST check.
3. Adapter compared `terminal_info().path` against the exe path, but MT5 reports the **install directory** → false mismatch. Caught by preflight.
4. `test_live_expected_mode_is_rejected` asserted a regex the message never contains.
5. Audit finding 1 — ranked tuples rendered name/score swapped (D-009).
6. Audit F1 — `RESOLVED` alias made every legacy scoring policy permissive (regression, fixed in D-010).
7. Audit F2 — alias list accepted bare `XAUUSD`; now pinned + `required_symbol_name` enforced.
8. Audit F3/F4 — account refusal now BLOCKED/2; policy registry single-sourced, `ValueError` no longer masked.
9. Post-audit — `expected_company` was parsed but never enforced; now checked in the account gate. `reject_on_mismatch` is now required to be `true` (fail-closed is not configurable) instead of being silently ignored.

### F7/F8 final review — CLOSED (2026-11-04)

Independent reviewer pass: `reports/AUDIT-PHASE1-F7F8.md`. Seven checks, **all PASS**, **no must-fix**.

| # | Check | Evidence |
|---|---|---|
| 1 | Changed code inspected line by line | `build_resolver_service` maps all 9 profile fields; single production construction site |
| 2 | F7 closed | blank `""` / `"   "` → `ConfigError`; wrong company → `CONNECTION_FAILED`, `account_gate_failed=True`; correct company passes |
| 3 | F8 closed | targeted tests pass; in-memory mutation of the wiring makes the test fail (`assert False is True`) |
| 4 | Full suite | `93 passed in 1.46s`, exit 0 (boundaries 5, config 23, logging 6, reporting 4, storage 6, identity 15, investigation 10, service 15, symbols 9) |
| 5 | Safety boundary unchanged | no order APIs in `src/` + `scripts/`; `MetaTrader5` confined to adapters; strict=AMBIGUOUS/ok=False, amended=RESOLVED/ok=False, identity=VERIFIED |
| 6 | Tree + evidence integrity | mtime delta equals the declared file set; `checks_sha256` `8bcc116f…` recomputed = stored |
| 7 | Acceptance | no blocker |

**Accepted residuals (recorded, not fixed — the audited tree is frozen):**
- **W1** `scripts/preflight.py` itself has no automated test; deleting its `build_resolver_service` call would keep the suite green. Runtime is correct today.
- **W2** `expected_company: str | None = None` means a future second construction site could skip the gate by omission. Unreachable from config today (loader rejects blanks).
- **W3** the two new tests are config→service wiring tests, not end-to-end gate tests. Wording corrected in this file and `CHANGELOG.md` after the audit.
- Evidence manifests still write `schema_version: 1` while `contracts.SCHEMA_VERSION` is 2 (format versioning lag, no safety impact).

## Phase 2 evidence (2026-11-04/05)

| Item | Result |
|---|---|
| Tests | `161 passed`, exit 0 — `evidence/pytest-20261104T220820Z.txt` |
| Live run | M1 3000 bars **0 gaps**, M5 3000 bars **0 gaps**, H1 3000 bars 4 gaps × 4 h — `evidence/collect-20261104T220820Z.txt` |
| Clock | broker = server time, UTC+2/+3 (EU DST); M1 stops ~21:55Z, resumes 23:00Z — model confirmed |
| Storage | 6000 bars ≈ 4.5 MB; 2 GB tick quota untouched |

### Defects found during Phase 2

1. Bar times treated as UTC — a fake 61-bar gap at the daily halt was the symptom. Fixed with a modelled broker clock.
2. A single measured offset mis-shifted pre-DST history (extra hour before 2026-10-25). Fixed by the EU DST model.
3. **Audit F1** — tick windows were passed to MT5 in UTC while the terminal expects server time (2 h shift, wrong ticks). Fixed + regression test.
4. **Audit F2** — gap runs merged across market closures, so a Friday→Sunday hole reported as a gap. Fixed: run flushes at every closure.

### Open items

- **F1 verification blocker (2026-11-04 22:28Z).** The tick-window clock fix and the server-relative freshness check are implemented and unit-tested, but the live re-verification ran during the daily halt (22:00–23:00Z), so no fresh ticks existed to measure the server clock. Every run therefore reports `DEGRADED: clock_unverified:no_fresh_ticks`. This is correct behaviour, not a failure — but it means F1 cannot be claimed verified today. Re-run the smoke between 23:00Z and 21:00Z the next day.
- Clock verification is inherently unavailable during the daily halt: timestamps still use the deterministic model, the run is flagged.
- H1 shows 4 × 4-bar holes in ~3000 bars — holiday/session artifacts, flagged rather than hidden.

## Known unknowns

U1 skill import UI flow · U2 custom MCP registration · U3 permission mode · U4 balance/equity (not authorized) · U5 spread/stop behaviour (spread observed 18 → 10 points across two days) · U6 swap/free-margin rules.

## Environment baseline

Windows 10 Pro 19045 x64 · i5-3337U · 8 GB RAM (~1.2 GB free) · C: 19.2 GB free, D: 123.9 GB free
Python 3.11.8 x64 (approved) · MT5 `C:\Program Files\Aron Markets MT5\terminal64.exe` build 6230 · DEMO / `AronMarkets-Demo` / USD / 1:400 · symbol `XAUUSD.`

## Phase 2 remediation (2026-11-05)

| Finding | State |
|---|---|
| A1 tick age | **PASS** — signed age, `|age| ≤ 5`, invalid stamps rejected; live `age = −2 s` accepted 5/5 |
| A3 / A4 tests | **PASS** — names match assertions; stamps computed per call |
| A6 offset setter | **PASS** — removed; the DST model is the only conversion authority (D-013) |
| A7 governance | **BLOCKED** — `approvals/A-07.json` is unverifiable; no record written |
| Historical ticks | **PASS (quarantined)** — replay `3087c765…` equals the original digest `799bc8c7…`; 7 840 rows unchanged, run `e01f4fe7…` quarantined pending human review |
| A2 window conversion | **PASS** — fixed after a live probe; request = `utc + offset`, first tick 0 s from the window start |

Suite `198 passed`, exit 0. Full record: `reports/PHASE2-REMEDIATION-REPORT.md`.
