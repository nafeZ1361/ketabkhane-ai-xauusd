# Phase 5 F3 — Independent Risk Revalidation at the Firewall Boundary

Status: **ACCEPTED — F3 12/12 (2026-11-27)**
Weight: **12 points**
Base: accepted F2 snapshot `a85bfc13ebb99ed034113540c7936ab57725341a` plus F2 acceptance-only documentation; branch `work/guardian-phase5-f3-risk-20261127`.

## 1. Frozen scope

Implement a pure, fail-closed risk revalidation function under `src/guardian/firewall/`. It independently recomputes the maximum safe lot size using the already accepted Phase 4 `RiskSpec` and `position_size` implementation, then checks a proposed lot size against that recomputed bound.

The risk specification is supplied separately by the trusted caller; it is never read from the untrusted request payload. Equity and stop distance are explicit function inputs. This gate does not establish the provenance of equity or the risk specification; authenticated provenance is a later integration concern. Tests use synthetic values only.

The result is a risk-validation decision, **not** an authorization to trade. F2 remains unchanged: every execution/order operation remains denied. No order construction, order API, MT5, broker connection, account read, approval change, DEMO activation, or LIVE path is in scope.

## 2. Frozen contract

- Inputs: exact `Decimal` values for equity, stop distance and proposed lots; exact `RiskSpec` type.
- Revalidate the supplied frozen `RiskSpec` by reconstructing it from its current fields before use; malformed or low-level-mutated state fails closed.
- Recompute the maximum allowed lots using Phase 4 `position_size(equity, stop_points, spec)`; do not trust a caller-supplied maximum.
- Proposed lots must be positive, at least `min_lot`, no greater than the recomputed maximum or `max_lot`, and an exact multiple of `lot_step`.
- Independently verify the proposed notional risk does not exceed `equity × risk_fraction`.
- Catch invalid arithmetic, malformed values and unexpected exceptions and return a DENY decision; never propagate a permissive fallback.
- Return an immutable decision with stable reason code and recomputed maximum. It must not mutate any input.
- Do not change `authorize_request` or grant any operation. F2's only ALLOW remains empty `POLICY_STATUS`.

## 3. Required tests and adversarial probes

1. Exact valid size and a smaller valid size pass risk validation.
2. Over-limit, off-step, below-minimum, non-positive and non-Decimal proposed sizes deny.
3. Invalid/non-finite equity and stop distance deny.
4. Invalid RiskSpec fields, wrong type and low-level frozen-object mutation deny.
5. Recomputed risk bound is checked independently; forged caller maximum is not accepted because no maximum parameter exists.
6. Phase 4 sizing arithmetic failures / Decimal exceptions deny.
7. Inputs remain unchanged; decision is immutable and deterministic.
8. F2 policy regression: execution, order, LIVE and financial-read operations remain denied; empty POLICY_STATUS remains the only allowed operation.
9. Static scan of new boundary module: no MT5, order, account, filesystem, process, network, or external dependency surface.
10. Independent mutation control makes the over-limit predicate permissive in a disposable copy; independent probes must detect the mutant.
11. Full suite, focused F3 suite, compileall, pinned wheelhouse/offline install, clean pip check, exact source archive/hash, frozen manifest before/after, and raw evidence sidecar verification.

No acceptance points are awarded for implementation or ordinary CI alone. F3 earns 12/12 only after one exact frozen target receives independent Inspector PASS with all applicable criteria above, verified workflow/harness pins and recomputed evidence hashes. Any missing or mismatched evidence is BLOCK; no partial points.

## 4. Explicit exclusions and limitations

- No actual account equity/balance/margin/profit read: A-04 is not granted.
- No order construction, order_check/order_send, MT5 import/use, broker connectivity, DEMO activation, LIVE operation or execution authorization.
- No change to Phase 4 sizing rules, user risk settings, broker profile, migrations, approvals, F2 policy or prior accepted phases.
- This gate validates arithmetic against the supplied specification; it does not prove that the caller's equity or specification is authentic. That requires a separately authorized, authenticated integration.
- Hosted CI Inspector is an isolated execution context, not an external human reviewer or proof of local Windows ACLs.



## 5. Exact F3 independent acceptance — D-039 (2026-11-27)

**Verdict: ACCEPTED — F3 12/12. Phase 5 progress: 34/100 (F1 10 + F2 12 + F3 12).**

- Exact inspected target: `3f02fc28cc8dfb3685d75e037588493cbbf998c6`.
- Independent workflow: [45898985819](https://github.com/nafeZ1361/ketabkhane-ai-xauusd/actions/runs/45898985819); Freeze job `140179835997` and Inspector job `140179938236`, both SUCCESS.
- Immutable Inspector harness pin: `0205030532305303941cdc58b05876182ec63fc0`.
- Focused F3 JUnit: **35 passed / 0 failures / 0 errors / 0 skipped**.
- Full Guardian JUnit: **506 passed / 0 failures / 0 errors / 0 skipped**; `compileall` exit 0.
- Independent black-box probes: **10/10 passed**; static boundary findings: **0**; mutation control detected the deliberately permissive size/risk mutant with **1 expected failure / 0 errors**.
- Frozen manifest: **259 files stable**; source TAR SHA-256 before/after: `a0b2c9b11d3b9bfddbfa198e9a998766cf14dba28a554ba8a62f6aa7ba2927e5`.
- Frozen-source artifact ID `15155185554`; downloaded ZIP SHA-256 `ed95ec1df1e648da367f8d52c2c1b57da23c9b5592dedf9f34a5ac890666fa27`.
- Evidence artifact ID `15154967843`; downloaded ZIP SHA-256 `00183d71ab05132de38cc4e5d93b95b1d0326bcafb59ad19234d41f8583c8f9c`. All **25** entries in `SHA256SUMS.txt` were independently recomputed and matched.
- Inspector SID `S-1-5-21-2315611937-1800655502-2561009274-1003`, distinct from runner SID `S-1-5-21-2315611937-1800655502-2561009274-500`; non-admin verified. Harness/frozen/evidence writes denied; test-copy/temp writes allowed. Ephemeral Inspector account removed after upload.
- Exactly eight wheel files matched `WHEELHOUSE.sha256`; hash-locked download, offline `--no-index --require-hashes` installation and `pip check` succeeded.
- Exact workflow summary verdict: PASS. Raw evidence and logs are in the linked run artifact.

**Limitations:** This is an owner-authorized isolated GitHub Actions Inspector context, not an external human reviewer and not proof of ACLs or Inspector identity on the owner's local Windows machine. F3 validates arithmetic against the separately supplied RiskSpec and explicit equity/stop inputs; it does not authenticate their provenance. A-04 remains absent. No account reads, MT5, broker connection, order construction/submission, DEMO activation or LIVE path was introduced. F2 remains unchanged and denies all execution/order operations. PR #8 remains Draft and unmerged.
