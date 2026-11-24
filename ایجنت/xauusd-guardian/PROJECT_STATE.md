# PROJECT_STATE

Last updated: 2026-11-24 (F1 developer remediation committed; independent acceptance pending)

## Phase status

| Phase | Status | Note |
|---|---|---|
| 0 Reconnaissance | DONE | 2026-11-03, `READY_WITH_BLOCKERS` |
| 0.5 Reconciliation | DONE | `PHASE_0_5_RESOLUTION.md` (workspace root), 4 blockers mapped |
| 1 Foundation | **PASS** (provisional, awaiting human sign-off) | structure, config, contracts, logging, storage, migrations, tests, identity resolver; three independent audit passes, no must-fix open |
| 2 Market data | **ACCEPTED** | Phase 2 accepted under A-08 (2026-11-05); see `reports/PHASE2-REMEDIATION-REPORT.md` and approval chain A-01→A-08 |
| 3 Analysis/strategy | **ACCEPTED (2026-11-20, D-022)** | S1–S7 PASS. S7 closed by an inspector run executed entirely under the `GuardianInspector` token (standard, non-admin, member of `Users` only; every write-class right explicitly denied on the frozen snapshot — all six access probes DENIED, read/list OK; ACL inheritance check 146 objects / 0 problems): junit **302 / 0 / 0** (46 migration cases, 2 pragma cases), `journal_mode=wal` + `synchronous=2` (FULL, D-020), storage probes all green (`revert_migration` refuses with ledger `[1,2,3]`; W3 `main.`-qualified; TEMP-homonym fail-closed; provenance refusal), snapshot manifest reproduced by the inspector before/after. `INSPECTED_REVISION = 1d489dde + c4bb33565fbec4af549f8d7788c7bdf080f34f1ece5f6c39198075ade823ac83` (120 files). Verdict `PASS` with disclosed residuals (D-022). See `artifacts/phase3-closure-20261120T1255Z.md` and `artifacts/inspector-run-20261120T124202/`. F2/F3 ADVISORY |
| 4 Risk | **ACCEPTED (2026-11-21, D-024)** | `PHASE4_PLAN.md`; `guardian/domain/risk/sizing.py` + 29 tests. S7 closed by an inspector run under the `GuardianInspector` token (write-denied snapshot; six/six probes DENIED; ACL check 247 objects / 0 problems) on commit `15a210a` (snapshot manifest `e939719f…56ca1`, 124 files; worktree == commit): junit **331 / 0 / 0** (46 migration + 2 pragma + 29 risk cases), `wal`+`synchronous=2`, storage probes green, independent black-box contract probe 31/31 (S1–S5 + cap), syntax gate green. Verdict `PASS` with disclosed residuals (R1/R2 in D-024). See `artifacts/phase4-inspection-20261121T1720Z.md` and `artifacts/inspector-run-20261121T164943/` |
| 4b Monte Carlo | **ACCEPTED (2026-11-21, D-027; D-026 S11 PASS)** | `MONTE_CARLO.md`; `domain/risk/montecarlo.py` + `scripts/montecarlo.py` + 30 tests; suite **361/0/0**; independent S11 PASS on commit `701a4dd`; snapshot SHA-256 `0eadf45e…`; Inspector evidence SHA-256 `7735b6a5…`; registration: `DECISIONS_LOG.md` D-027. |
| 5 Firewall | **ENTRY READY — F1 DEVELOPER IMPLEMENTATION COMMITTED; INDEPENDENT ACCEPTANCE PENDING** | D-028; frozen F1-F8 weights remain 100. F1 candidate HEAD `081e0303ef605a918b6c9104efa34fee8b17a5e8`; developer remediation report `HANDOFF/artifacts/REPORT-PHASE5-F1-REMEDIATION-20261124.md`; evidence `evidence/phase5-F1-remediation-20261124T1741Z.txt` SHA-256 `8adaf28f65f0cde0dabb004a55d8da0d8b004342c39e3b5f46dd696567d7c711`. Guardian CI run `45451231751` succeeded (Python 3.11.9; 439 pytest progress dots to 100%; compileall step succeeded). CI & Evidence Gate run `45451244959` succeeded: Python 3.10 and 3.12 each 120 passed, 0 failures/errors, 95.77% coverage; encoding guards and evidence uploads succeeded. F1 remains **0/10 accepted points** until independent, read-only GuardianInspector PASS on this exact frozen commit. F2-F8 remain NOT STARTED; Phase 5 accepted completion remains 0/100. PR #8 remains Draft/unmerged. Residuals unchanged: D-4 OPEN/ADVISORY, D-2 owner-accepted, D-3 preserved/unused, D-019 DEFERRED, PHASE2-CLOCK-RECHECK-1 OPEN. No MT5/order/account/LIVE action. |
| 6 Backtest | NOT STARTED | |
| 7 Monitoring | NOT STARTED | |
| 8 Integration | NOT STARTED | |
| 9 Independent audit | NOT STARTED | |
| 10 Remediation | NOT STARTED | |
| 11 DEMO readiness | PRE-REGISTERED / WAITING FOR PHASE 10 | Readiness only; no order activity in Phase 11. A-09 governs a separate post-acceptance Phase 12 test |
| 12 DEMO execution validation | **PRE-REGISTERED / BLOCKED** | D-030 / A-09: one 4h30m autonomous DEMO test after Phase 11 independent PASS; A-04 and risk-sizing/account-data gate still unresolved |

## Approvals held

- A-01 workspace creation — APPROVED (2026-11-04)
- A-02 venv + pinned dependencies — APPROVED (2026-11-04)
- A-03 local git repository — APPROVED (2026-11-04)
- A-06 implement D-003 identity resolver + reporting fixes — APPROVED (2026-11-04, `approvals/A-06.json`)
- A-07 Phase 2 implementation — **SUPERSEDED BY A-08 as evidence**; retained unchanged as history
- A-08 Phase 2 scope confirmation and acceptance — **GRANTED** (2026-11-05, `approvals/A-08.json`, `record_sha256=d7126270…`)

## Open approvals

- (none for Phase 2 — A-08 granted; A-04/A-05 below remain closed)- A-04 balance/equity access — NOT REQUESTED (synthetic fixtures only)
- A-05 DEMO-level order checks / DEMO execution — NOT GRANTED (historical; Phase 12 one-time scope is separately authorized by A-09)
- A-09 post-completion Phase 12 autonomous DEMO validation — GRANTED, conditional on Phase 11 independent PASS; one use only
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
- **`PHASE2-CLOCK-RECHECK-1` attempt 1 (2026-11-21T17:10Z): BLOCKED — market closed (Saturday).** The smoke ran, the DEMO terminal connected, and it returned 5 historical M1 bars with 0 gaps; with no fresh ticks the run correctly reported `DEGRADED: clock_unverified:no_fresh_ticks` — no PASS claimed or simulated. Evidence: `evidence/phase2-clock-recheck-20261121T171004Z.txt` (`2b298b75…cb21` + sidecar). Re-run in a live session between the Sunday open (23:00Z) and the next 21:00Z halt; the ticket stays OPEN.
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

## Phase 3 / S7 evidence (2026-11-15)

| Item | Result |
|---|---|
| HEAD inspected | `e56b3a6` — tree `8ad3949e…`, worktree clean, **279 passed**, `compileall` exit 0 |
| Round-4 verdict | round-3 must-fix M1/M2/M3 **closed by execution**; two new defects found (N1 evidence manifest, N2 identifier parsing) |
| Fixes | `db.py` `_bare_identifier` + `_SCHEMA_PREFIX`; 3 regression tests; `MANIFEST.sha256` regenerated (11/11 verify) |
| Post-fix suite | **282 passed**, exit 0; `compileall` exit 0 |
| Adversarial probes | **15/15**, exit 0 — legacy DB, `TEMP`, `ATTACH`, hostile down-script, drift, quoted/bracketed/backticked identifiers |
| Evidence | `evidence/phase3-S7-20261115T171715Z.txt`, `evidence/phase3-S7R5-20261115T174829Z.txt`, `evidence/phase3-S7R7-20261115T184319Z.txt` (each with `.sha256`) |
| Reports | `HANDOFF/artifacts/REPORT-S7-ROUND4.md`, `REPORT-S7-ROUND5.md` (independent, BLOCK), `REPORT-S7-ROUND5-REMEDIATION.md` |
| S7 status | S7 **PASS** (independent round 8). Phase 3 remains **OPEN** pending an independent inspection of the option-3 change (destructive reverse removed) |
| Commit | none — changes are uncommitted, no push performed |

## Verification pass (2026-11-19)

| Item | Result |
|---|---|
| HEAD | `1d489dde` (this workspace; the project has no separate git history) |
| Suite | `300 passed`, exit 0 — `evidence/gate-verify-20261119T194038Z.txt` |
| compileall | exit 0 — same evidence file |
| Collection defect | fixed: two research modules (`test_stageB_leakage.py`, `test_research_features.py`) aborted collection at HEAD; scoped out via `tests/conftest.py` `collect_ignore`, both files untouched (D-019) |
| Option-3 inspection | `REPORT-OPT3-INSPECTION.md` → **PASS**, 0 must-fix; W1/W2/W3 non-blocking |
| W1 | resolved: `REPORT-F1-OPTION3.md` exists (4,395 bytes) |
| W2 | fixed 2026-11-19 in five places (D-019); no behaviour change |
| W3 | **fixed 2026-11-19**: emitted SQL now uses `DELETE FROM main.<table>`; evidence `evidence/phase3-w3-20261119T203654Z.txt` (advisory, not gated) |
| Unsupported claim | the handoff header cites `REPORT-CONFIRMATION-2.md`; no such file exists in this tree |
| Owner decision pending | relocate the two research test modules out of this project |

## Remediation pass (2026-11-20)

| Item | Result |
|---|---|
| Baseline HEAD | `1d489dde` — the project has no separate git history; acceptance pins the worktree snapshot, not HEAD |
| F-1 durability | **REVERTED** — `PRAGMA synchronous = NORMAL` removed from `connect()`; connections use SQLite's default FULL (2). Decision D-020. Tests: `test_wal_and_default_synchronous`, `test_synchronous_contract_holds_for_every_new_connection` |
| Record conflict | `HANDOFF/artifacts/PHASE3-FINAL-HANDOFF.md` closure claim **withdrawn**; the cited `REPORT-CONFIRMATION-2.md` is not in this repository (only outside it, `C:\\GS7\\review-final\\`), so it is not claimed as evidence |
| BOM claim | **corrected, not restored** — `tests/unit/test_migration_reversal.py` starts `22 22 22` (no BOM); the HEAD blob starts `EF BB BF`; D-019 corrected by D-020 |
| Research modules | **NOT_RUN / out_of_scope** — `PHASE3_PLAN.md` §1 excludes ML frameworks and §8 excludes profitability work; both files test `scripts/research_edge.py` (pandas+numpy+sklearn) and are not Phase 3 deliverables (D-021). `collect_ignore` is collection scope, not PASS. Execution would need an owner-approved external venv or the D-019 relocation |
| Suite | `302 passed`, exit 0 (after the F-1 revert and its two tests) |
| Phase 3 status | **NOT closed** — a fresh independent inspection of the current snapshot is still required |
| BOM correction | `evidence/phase3-bom-correction-20261119T212414Z.txt` (`99762d78…5388`) supersedes the false “BOM restored” claims; originals untouched |
| Inspection package | `artifacts/phase3-inspection-package.md` (workspace root, outside this snapshot) — prepared, not executed |

## Phase 2 clock recheck — PHASE2-CLOCK-RECHECK-1 (2026-11-20)

| Item | Result |
|---|---|
| Run | 2026-11-20T13:36:32Z–13:36:34Z, market open, read-only adapter |
| Model offset | `7200 s` (UTC+2, post-DST) |
| Measured offset | `7200 s`, MAD `0` over `10` samples |
| Verdict | **PASS** — fresh ticks existed and the measured broker offset equals the model; `clock_unverified:no_fresh_ticks` did not recur |
| Safety | No balance/equity/margin/profit read; no order API; adapter detached |
| Evidence | `evidence/phase2-clock-recheck-20261120T133632Z.txt` (`920cfef6…2588`) |

## Phase 4 — risk sizing (2026-11-21)

| Item | Result |
|---|---|
| Authorisation | owner mission "FINISH & PUBLISH"; scope frozen in D-023 **before** code |
| Module | `src/guardian/domain/risk/sizing.py` — `RiskError`, `RiskSpec`, `position_size` |
| Tests | `tests/unit/test_risk_sizing.py` — 29 cases (risk-bound grid, step/cap, monotonicity, fail-closed matrix, AST safety scan) |
| Suite | **331 passed**, exit 0; `compileall` exit 0 |
| Safety | no MT5/account/order surface; migrations `0001`–`0003` untouched; DEMO-only unchanged |
| Acceptance | **OPEN** — S7 independent PASS not obtained; Phase 4 is implemented, not accepted |

## Phase 3 closure (2026-11-20, D-022)

| Item | Result |
|---|---|
| Verdict | **`PASS` — Phase 3 ACCEPTED** |
| Inspector | `GuardianInspector` token: standard account, `Users` only, not in `Administrators`; write-class rights explicitly denied on the snapshot (six/six probes DENIED, read/list OK); §6.2 inheritance check: 146 objects, 0 problems |
| INSPECTED_REVISION | `1d489dde + c4bb33565fbec4af549f8d7788c7bdf080f34f1ece5f6c39198075ade823ac83` (120 files; manifest reproduced by the inspector before/after and independently on the live tree) |
| Suite | junit `302 / 0 / 0`, exit 0 |
| Migration tests | 46 cases (same junit run) |
| Durability | `journal_mode=wal`, `synchronous=2` (FULL; D-020) |
| Storage probes | all green: `revert_migration` refuses; W3 `main.` qualification; TEMP-homonym fail-closed; provenance refusal |
| Machine-readable | `RESULT_JSON …"all_green":true` — `artifacts/inspector-run-20261120T124202/inspector-evidence-v2-20261120T124202.txt` (`031e2a06…7a76`) |
| Doc fixes | 4/4 under owner authorization — `evidence/phase3-docfix-20261120T1045Z.txt` (`2eb2a3a0…9093` + sidecar) |
| D-019 | **DEFERRED (formal, owner decision)** — research modules stay `out_of_scope` / `NOT_RUN`; not Phase 3 acceptance criteria |
| Phase 2 clock | split out as ticket `PHASE2-CLOCK-RECHECK-1` (re-run smoke between 23:00Z–21:00Z) — not a Phase 3 condition |
| Disclosure | harness-provenance residual recorded in D-022: harness pinned by hashes, W3 shield mutation-proven (breaking the line fails suite test + probe), raw logs archived with hashes |
| Git | no commit/push; acceptance pinned by the manifest hash above, not by a commit id |

## Phase 4 closure (2026-11-21, D-024)

| Item | Result |
|---|---|
| Verdict | **`PASS` — Phase 4 ACCEPTED** |
| Inspector | `GuardianInspector` token: standard, `Users` only, not in `Administrators`; six/six write-class probes DENIED on the snapshot; §6.2: 247 objects, 0 problems |
| Commit | `15a210a05c16744b9f114b13a86a76871b77b27c` (HEAD; parent `87084eb`) |
| Snapshot | `git archive` of the commit → manifest `e939719fb6c3aed5fa98291cc844d9f50948116eb082702d92e0e8c0d8956ca1` (124 files); inspector reproduced before/after; `git diff` vs commit empty |
| Suite | junit `331 / 0 / 0`, exit 0 (46 migration + 2 pragma + 29 risk cases) |
| Contract probes | independent black-box probe from `PHASE4_PLAN.md` §2 / D-023: 31/31 PASS (S1–S5 incl. cap clamp; full fail-closed matrix) |
| Durability | `journal_mode=wal`, `synchronous=2` (FULL; D-020) |
| Pinned hashes | `sizing.py fdebd07c…ea1f3`; `test_risk_sizing.py 0f335f5a…0153e53`; `db.py 177c3330…5c20` (untouched) |
| Machine-readable | `RESULT_JSON …"all_green":true` — `artifacts/inspector-run-20261121T164943/inspector-evidence-v3-20261121T164943.txt` (`855f2cb2…5041`) |
| Report | `artifacts/phase4-inspection-20261121T1720Z.md` (delivered) |
| D-019 | remains **DEFERRED** (untouched by this decision) |
| R1/R2 | disclosed: harness provenance + two first-run scan false positives corrected and re-run; both evidence sets preserved |
| Git | no commit/push by the inspector; HEAD is the accepted commit; registration docs are uncommitted worktree changes |


## D-029 completion path — 2026-11-22

- Engineering work continues through Phase 11; live execution is not required for engineering completion.
- Phase 5 remains blocked only until its entry gates are evidenced, with D-008 the immediate blocker.
- Phases 6–11 require separate pre-registered plans before implementation; no weights are assigned until those plans are approved.
- Post-completion Live Verification is deferred to an owner-run validation. The owner will return raw evidence for a separate PASS/FAIL/BLOCKED/REMEDIATION verdict.
- Safety unchanged: DEMO disabled pending A-05 + explicit authorization; A-04 absent; no LIVE mode/order submission; no destructive operations or unrelated-project changes.


## D-008 — offline dependency closure (candidate carried forward, 2026-11-22)

| Item | Result |
|---|---|
| Source | Candidate package from commit `234e73ea2586e393deb401a289681cbd9bcf6165` |
| Isolation / closure | Python 3.11.8 hermetic venv; eight pinned distributions; hashed lock and wheel manifest added |
| Engineering evidence | Source report records offline install with unreachable index, clean `pip check`, 361 tests passed, and `compileall` exit 0 |
| Residual | Read-only attribute is not an ACL boundary; wheelhouse binaries are external to Git |
| Integration status | **CANDIDATE — fresh independent inspection of this integrated snapshot required; no inherited PASS** |

## D-008 independent inspection and administrative follow-ups (2026-11-23)

- Inspected code snapshot: `integration/d008-offline-closure-20261122` at `cc106b557586e3e4cd867897c642ae7dc7d3fd16`.
- Independent Inspector verdict: **PASS**. Report SHA-256: `029d9e9546514b4c058786c950abb542ef117a1361ae8fbe4f5318714b17079c`.
- Mirrored agent-log files: byte-identical; both SHA-256 `3ead974ca6109d9754e3c3fe3195f801fb60950036c475d0fc3534abdc2c474a`.
- D-1: **APPLIED / INDEPENDENTLY VERIFIED** on the PR #8 verification worktree: Windows ReadOnly bit set on WHEELHOUSE.sha256 and requirements-hashed.lock; hashes unchanged and write-open denied. This is an operational attribute only, not ACL protection.
- D-2: **OWNER ACCEPTED — NON-BLOCKING FOLLOW-UP** (2026-11-23). No ACL modification authorized or performed. Future snapshots must be created under an Owner-only root/path with restrictive inheritance and independently verified effective access.
- D-3: **VERIFIED / UNUSED / PRESERVED**. External lock SHA-256 `404f36ed4512d1ac97c4b5d4a64f3bff152b07a3e3754224e734c28670126b8c`, mismatching the committed lock SHA-256 `ed42dbdc2c65bb1393c1313e9ffdc897badb615d41e41e337ab8109db1b81970`. It remains unchanged.
- D-4: Inspector supplied full suite result **374 / 0 / 0** and builder verification evidence; the prior developer omission is disclosed, not hidden.
- Administrative D-008 status: **ACCEPTED WITH DISCLOSED D-2/D-4 RESIDUALS; AP-7 INDEPENDENT INSPECTION SATISFIED**. AP-7 PASS on exact PR #8 head `177cf62...` (report `47a9e1f6...`; Inspector SID `...-1004`, logon ID `S-1-5-5-0-1350151026`, session 25; 377/0/0; manifest `34ac...` before=after). D-4 remains **OPEN/ADVISORY** and non-blocking; D-2 old-root exposure remains owner-accepted; no ACL remediation is claimed. Phase 5 entry remains subject to the separate formal gates; current preflight evidence is the outstanding gate-2 component.
- The current work branch received the AP-7 independent inspection on exact head `177cf62...` (PASS; report `47a9e1f6...`). This acceptance record is documentation-only.

## Phase 5 entry remediation on work branch (2026-11-23)

- Work branch: `work/guardian-phase5-entry-20261123`
- Latest CI-verified commit: `20de160a487247b86e3414108bf064ac113191d8`
- Redaction fix: `src/guardian/observability/logging_setup.py` now scrubs arbitrarily nested dict/list/tuple values, financial fields (including `margin*`), credential-like keys and embedded strings; formatter redacts structured `run_id` as well as the message.
- Regression tests added/expanded in `tests/unit/test_logging_redaction.py`; Windows GitHub Actions run `45175590370` completed SUCCESS. Pytest progress: 377/377; compileall step completed successfully.
- Nested `AGENTS.md` authority/precedence clarified: repository-root baseline applies repository-wide; nested Guardian instructions add stricter subtree rules; stricter rule wins on conflict.
- **AP-7 acceptance:** independent read-only Inspector PASS on the frozen work-branch snapshot at `177cf62...` (SID `...-1004`; logon ID `S-1-5-5-0-1350151026`; session 25; report `47a9e1f6...`; 377/0/0; manifest `34ac...` before=after). Redaction/config/API/nested-data and AGENTS scope verified. D-4 remains OPEN/ADVISORY. **Phase 5 entry remains BLOCKED on current preflight evidence**; no F1-F8 work started.
- No MT5 order code, DEMO activation, new dependency, account-field access, or LIVE functionality was added.


## AP-7 acceptance and Phase 5 entry evaluation (2026-11-23)

| Gate (PHASE5_PLAN.md) | Status | Evidence |
|---|---|---|
| 1. Phase 4/4b acceptance records | **MET** | D-024 report `539a38e7...f51b` and raw evidence `b51fda69...e4f5`/`855f2cb2...5041` verified; D-027 primary `7735b6a5...8c28` and JUnit `91bb5ab6...986a` verified. Records committed; raw artifacts local/gitignored, traced by hash. |
| 2. D-008 closure (hermetic, hashes, offline, suite, preflight) | **PARTIAL / BLOCKING** | AP-7 verifies Python 3.11.8 hermetic, 8 pinned wheels, offline install, `pip check`, `builder --verify`, **377/0/0**, `compileall`. **Preflight evidence for the current target is absent**; only Phase 2-era preflight JSONs exist. |
| 3. D-028 owner-approved scope/weights | **MET** | D-028 frozen F1-F8 = 100; plan is `PHASE5_PLAN.md`. |
| 4. Redaction cannot be disabled; negative tests | **MET** | AP-7 content checks: formatter/API no off-switch, config forced true; redaction tests pass in 377/0/0. |
| 5. Nested AGENTS scope/authority | **MET** | AP-7 content check passes; nested authority/precedence is explicit. |

- CI at `177cf62...`: runs `45214875542`, `45214875514`, `45214859520` all SUCCESS; check-runs `test`, `test (3.10)`, `test (3.12)`, `test` all success. CI is corroborating; the AP-7 local suite is authoritative.
**Phase 5 verdict: `PHASE5_ENTRY_BLOCKED`** on missing current preflight evidence. F1-F8 remain NOT STARTED (0/100). No merge, Phase 5 implementation, DEMO activation, order construction/submission or trading.