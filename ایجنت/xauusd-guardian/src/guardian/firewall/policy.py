"""Central fail-closed authorization policy for the Phase 5 firewall.

F2 only. This module is pure: it performs no I/O, reads no approvals, imports no
broker adapter, and cannot construct or submit an order. Until a later, separately
accepted phase replaces this policy, only a non-sensitive policy-status request
may be allowed.
"""

from __future__ import annotations

from dataclasses import dataclass

from guardian.contracts.firewall import FirewallRequest


@dataclass(frozen=True, slots=True)
class PolicyContext:
    """Minimal trusted runtime scope supplied by the firewall host."""

    phase: int
    account_mode: str


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Immutable authorization outcome; ALLOW is not an execution capability."""

    allowed: bool
    reason_code: str


# These names are recognized only to return stable, explicit denial reasons.
_EXECUTION_OPERATIONS = frozenset(
    {
        "DEMO_EXECUTION",
        "ORDER_CHECK",
        "ORDER_SEND",
        "ORDER_MODIFY",
        "ORDER_CLOSE",
    }
)
_LIVE_OPERATIONS = frozenset({"LIVE_EXECUTION", "LIVE_ORDER_SEND"})
_FINANCIAL_READ_OPERATIONS = frozenset(
    {"ACCOUNT_FINANCIAL_READ", "READ_BALANCE", "READ_EQUITY", "READ_MARGIN", "READ_PROFIT"}
)
_STATUS_OPERATIONS = frozenset({"POLICY_STATUS"})


def authorize_request(
    request: FirewallRequest, *, context: PolicyContext
) -> PolicyDecision:
    """Evaluate one typed request and deny every unrecognized or out-of-scope case.

    F2 intentionally grants no DEMO execution, LIVE execution, order operation,
    or account-financial-data access. A-09 is Phase 12-only and cannot authorize
    any Phase 5 operation. F6's disabled execution boundary remains authoritative.
    """
    if type(request) is not FirewallRequest:
        return PolicyDecision(False, "INVALID_REQUEST_TYPE")
    if type(context) is not PolicyContext:
        return PolicyDecision(False, "INVALID_POLICY_CONTEXT")

    # Exact types prevent bool/int and str-subclass surprises in security fields.
    if type(context.phase) is not int or context.phase != 5:
        return PolicyDecision(False, "PHASE_SCOPE_MISMATCH")
    if type(context.account_mode) is not str:
        return PolicyDecision(False, "INVALID_ACCOUNT_MODE")
    if context.account_mode != "DEMO":
        return PolicyDecision(False, "ACCOUNT_MODE_NOT_ALLOWED")

    operation = request.message_type
    if type(operation) is not str or not operation:
        return PolicyDecision(False, "INVALID_OPERATION")

    if operation in _LIVE_OPERATIONS:
        return PolicyDecision(False, "LIVE_MODE_PROHIBITED")
    if operation in _FINANCIAL_READ_OPERATIONS:
        return PolicyDecision(False, "A04_NOT_GRANTED")
    if operation in _EXECUTION_OPERATIONS:
        return PolicyDecision(False, "DEMO_EXECUTION_DISABLED_IN_PHASE_5")
    if operation in _STATUS_OPERATIONS:
        if request.payload:
            return PolicyDecision(False, "STATUS_PAYLOAD_NOT_ALLOWED")
        return PolicyDecision(True, "POLICY_STATUS_ONLY")

    return PolicyDecision(False, "UNKNOWN_OR_UNAUTHORIZED_OPERATION")
