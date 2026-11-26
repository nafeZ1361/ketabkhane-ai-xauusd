# Phase 5 F4 — Restricted Worker Process and Authenticated Replay-Resistant IPC

Status: **PRE-REGISTERED — IMPLEMENTATION NOT VERIFIED**
Weight: **15 points**
Base: F3 final branch HEAD \`9a4113be8a5b16ebd141c2b429f40f6946c0688f\`
Branch: \`work/guardian-phase5-f4-ipc-20261127\`

## 1. Frozen scope

Create a narrowly scoped, separately launched Windows worker process for pure Guardian computations and a bounded, authenticated, replay-resistant request/response protocol between the parent and worker. The worker is not an execution process. It must not import MT5, read account data, construct orders, connect to a broker, or perform arbitrary filesystem/network/process operations.

F4 is infrastructure only. F2 remains authoritative and denies all execution/order operations. F3 risk validation remains arithmetic-only. No DEMO activation, order check/send/modify/close, LIVE path, A-04/A-05 change, approval mutation, dependency addition, or Phase 4 rule change.

## 2. Frozen process-isolation contract

- Windows is the supported runtime for this gate; unsupported platforms fail closed.
- Launch the exact configured Python interpreter and fixed worker module/script. No shell, no user-controlled executable, arguments, import path, working directory, or environment overlay.
- Require the parent to run with a verified non-elevated Windows token: `TokenElevation=0`, Medium integrity (RID 8192), Administrators SID absent or deny-only, and only `SeChangeNotifyPrivilege` may be enabled (all other privileges must be disabled). Launch the worker with the same non-elevated identity; never elevate or fall back to an elevated process. Refuse startup if the parent token fails these checks. This is not a separate restricted-SID/AppContainer filesystem sandbox; filesystem access remains limited by the invoking user's DACL. The worker source is fixed and statically inspected to exclude filesystem/network APIs.
- Place the worker in a Windows Job Object with kill-on-close, active-process limit 1, and explicit process-memory and CPU-time limits. Job assignment failure terminates the child and fails closed.
- Inherit only the dedicated IPC handles. Close unrelated handles; do not pass secrets in argv or environment. Use a minimal deterministic environment and a dedicated empty working directory.
- Enforce a startup timeout, per-request timeout, bounded frame sizes, bounded response sizes, and deterministic termination/reaping on timeout, malformed output, protocol error, or parent shutdown.
- Worker stdout is protocol-only. Diagnostics are not permitted to contain request payloads, keys, account identifiers, or secrets; stderr is bounded, retained only as a short diagnostic, and redacted before surfacing.
- Worker imports only the allowlisted Guardian contracts/domain/firewall modules required for pure operations. Static inspection must find no MT5, order, account, filesystem, network, shell, or subprocess capability in worker code.

## 3. Frozen IPC protocol

- Use length-prefixed UTF-8 JSON frames with a strict maximum of 64 KiB; reject zero/oversized/truncated frames, invalid UTF-8, duplicate keys, unknown fields, non-finite numbers, excess nesting, and non-canonical or malformed envelopes.
- Protocol version and message types are exact allowlists. Unknown versions, message types, fields, or payload shapes fail closed.
- Parent creates a fresh 256-bit session identifier and 256-bit HMAC key for every worker lifetime using \`secrets\`; deliver key material only through a dedicated inherited anonymous pipe/handle, never argv, environment, logs, or repository files.
- Authenticate every request and response with HMAC-SHA256 over canonical JSON bytes; compare tags with \`hmac.compare_digest\`. Domain-separate request and response tags.
- Every frame binds protocol, version, session identifier, strictly increasing sequence number, message type, and payload. Reject stale, duplicate, skipped, out-of-order, cross-session, wrong-direction, and replayed frames. Session rotation on every restart makes prior-session frames invalid.
- Parent validates response sequence/session/type and request correlation before accepting a response. Any authentication or protocol failure poisons the session and terminates the worker; never continue with a partially trusted channel.
- No persistent key storage. Session state is memory-only and discarded on shutdown. This is session-scoped replay resistance, not a claim of cross-host or durable replay protection.
- Allowed operations are limited to health/status and pure synthetic-input risk revalidation. No operation maps to order or account access.

## 4. Required tests and adversarial probes

1. Worker token: child is non-elevated; Medium integrity is verified; Administrators SID is absent or deny-only; only `SeChangeNotifyPrivilege` may be enabled; all other privileges are disabled; Job Object limits and assignment/kill-on-close are effective.
2. Process launch: exact interpreter/module, no shell, minimal environment, only intended handles inherited; unsupported OS and restriction failure deny without fallback.
3. Lifecycle: startup/request timeout, malformed output, worker crash, parent shutdown, kill/reap and no orphan child.
4. Frame parser: length bounds, truncation, invalid UTF-8, duplicate JSON keys, nesting/size limits, unknown fields/version/type, NaN/Infinity, malformed canonical envelope.
5. Authentication: valid request/response accepted; tampered payload/tag, wrong key, wrong direction and invalid correlation rejected.
6. Replay/order: duplicate, stale, skipped, out-of-order and cross-session sequence/session frames rejected; restart rotates session and key.
7. Secret handling: key absent from argv/env/logs/files; bounded redacted diagnostics; no raw payload/credential leakage.
8. Policy regression: F2 continues to deny all execution/order/LIVE/financial-read operations; only empty POLICY_STATUS remains allowed. F3 arithmetic contract remains unchanged.
9. Static worker boundary: no MT5, order APIs, account reads, network, arbitrary file access, shell, or process-spawn surface beyond the single parent-controlled launch.
10. Mutation controls: deliberately disable HMAC verification, replay tracking, or Job Object assignment in disposable copies; independent probes must detect each mutant.
11. Focused tests, full suite, compileall, pinned wheelhouse/offline install, clean pip check, exact frozen archive/hash, manifest stability, and raw evidence sidecar verification.

## 5. Acceptance and evidence

F4 earns **15/15 only** after implementation, focused positive/negative/adversarial tests, all required mutation controls, full regression and compileall, independent static/black-box inspection, exact frozen snapshot, separately pinned Inspector harness, restricted-identity/ACL evidence, raw evidence upload, and independently recomputed hashes. Any missing/mismatched evidence is BLOCK; no partial points. Developer/CI success is not independent acceptance.

The Inspector must verify the exact triggering source commit, immutable harness pin, source archive before/after identity, separate restricted Inspector identity, offline hash-pinned dependencies, all test results, mutation detections, and every evidence sidecar digest. No repository write token or secrets may be exposed to target code.

## 6. Explicit exclusions and limitations

- No MT5 import/use, broker connection, account financial-field reads, order construction/submission/check, DEMO activation, LIVE operation, or execution authorization.
- No network listener, TCP/UDP socket, named-pipe server, persistent credential, external PKI, new dependency, migration, database write, or approval change.
- Session replay protection is limited to one ephemeral authenticated worker session; durable cross-restart replay protection is not claimed.
- Worker process must inherit a verified non-elevated token and be assigned to the verified Job Object; elevated parent contexts fail closed. No separate restricted-SID or AppContainer filesystem sandbox is claimed.
- F4 does not make the worker safe to host untrusted arbitrary Python. Only the fixed worker entry point and typed allowlisted operations are in scope.
