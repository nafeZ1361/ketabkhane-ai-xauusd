# Phase 5 F4 — Restricted Worker and Authenticated Replay-Resistant IPC

Status: **IMPLEMENTED / INDEPENDENT INSPECTION PENDING — 0/15**
Base: accepted F3 snapshot `9a4113be8a5b16ebd141c2b429f40f6946c0688f`.
Branch: `work/guardian-phase5-f4-worker-20261127`.

## Frozen scope

F4 implements a fail-closed restricted Windows worker boundary and authenticated,
replay-resistant localhost IPC. It does not authorize DEMO execution, construct
orders, connect to MT5, read account financial fields, enable approvals, or add
LIVE capability.

## Controls implemented

- Windows `CreateRestrictedToken` with `DISABLE_MAX_PRIVILEGE`; no unrestricted
  fallback.
- Anchored Python executable path; worker is launched only through the F4 launcher.
- One-shot bootstrap material is sent through inherited stdin, not argv or logs.
- Loopback-only TCP transport.
- Per-launch 256-bit HMAC key and 128-bit session nonce.
- Canonical JSON HMAC-SHA256 framing.
- Strict monotonic sequence numbers; duplicate/replayed/out-of-order frames deny.
- Timestamp freshness bound; stale frames deny.
- Exact envelope fields and bounded frame size.
- Worker hello must prove restricted-token state and expected PID before readiness.
- Worker has no execution/order API; all non-shutdown messages return an explicit
  non-execution denial.
- Startup failure, authentication failure, handshake failure and lifecycle failure
  are fail-closed.
- Shutdown is authenticated, waits for termination, and force-terminates only the
  already-restricted worker if graceful shutdown fails.
- Process/thread handles are closed on all launcher paths.

## Security correction

The first F4 design review identified that UAC elevation type is not a sufficient
predicate for worker restriction. The implementation therefore uses
`TokenHasRestrictions` as the restriction predicate and treats elevation type
only as diagnostic metadata. This is intentional: UAC state and restricted-token
state are different security properties.

## Required independent acceptance

The Inspector must verify the exact frozen candidate with:

1. focused F4 tests and full Guardian suite;
2. compileall and dependency/pip-check regression;
3. IPC replay, forgery, nonce, stale-frame and malformed-envelope probes;
4. worker-token restriction verification on Windows;
5. lifecycle/crash/handshake failure probes;
6. static scan proving no order/MT5/account/approval surface;
7. disposable mutation control that makes authentication or replay checks permissive;
8. immutable source manifest and recomputable evidence hashes;
9. separate Inspector execution context and pinned harness.

No points are earned until independent PASS. If restricted-token creation or verification
cannot be reproduced safely, F4 remains BLOCKED/0 rather than falling back to an
unrestricted worker.

## Safety

No A-04 account reads, A-05 DEMO activation, order construction/submission,
MT5 connectivity, LIVE mode, approval mutation, dependency addition, destructive
operation, merge, force-push or history rewrite is authorized.
