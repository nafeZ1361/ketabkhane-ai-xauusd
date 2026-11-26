# Phase 5 F3 — Independent Risk Revalidation at the Firewall Boundary

Status: **PRE-REGISTERED / IMPLEMENTATION NOT YET VERIFIED**
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

