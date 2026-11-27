# Phase 5 F5 — Persistent Fail-Safe Kill Switch and Recovery Semantics

Status: IMPLEMENTATION IN PROGRESS — 0/15
Base: F4 accepted HEAD c2bf2d455dc8ea7351260f3fdb88778404f2d274.
Branch: work/guardian-phase5-f5-kill-switch-20261127.

## Frozen scope

F5 adds a persistent, fail-safe kill-switch state boundary. It does not enable DEMO
execution, construct orders, connect to MT5, read account financial fields, alter
approvals, or add LIVE capability.

## Required behavior

- Default-deny / fail-safe: missing, unreadable, malformed, unsupported-version,
  ambiguous, or invalid state is treated as KILL ACTIVE.
- Persistent state survives process restart.
- State writes are atomic: write a complete canonical record to a same-directory
  temporary file, flush it, fsync it where supported, then replace the state file.
- Activation is fail-safe: if persistence cannot be confirmed, the caller receives
  failure and the effective state remains ACTIVE.
- Recovery is explicit only; restart must never auto-clear the kill switch.
- Recovery uses compare-and-swap generation semantics so stale recovery attempts
  cannot clear a newer state.
- Unknown JSON fields, wrong types, invalid generation, invalid state, invalid
  version and non-canonical records fail closed.
- No secrets, credentials, account fields, broker data, network access or external
  dependencies.
- The API exposes state/activation/recovery only; it is not an execution
  authorization API.

## Acceptance

Focused positive/negative/concurrency/restart/persistence-failure tests; mutation
probe proving fail-open corruption handling is detected; full suite + compileall;
static scan proving no order/MT5/account/approval surface; immutable source manifest
and recomputable evidence hashes; independent read-only Inspector on an exact frozen
snapshot using a separately pinned harness.

No points until independent PASS.
