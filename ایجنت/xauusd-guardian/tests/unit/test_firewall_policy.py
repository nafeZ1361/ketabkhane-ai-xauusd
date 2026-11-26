"""F2 central fail-closed policy tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from guardian.contracts.firewall import FirewallRequest
from guardian.firewall.policy import PolicyContext, authorize_request


NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
CONTEXT = PolicyContext(phase=5, account_mode="DEMO")


def request(message_type: str, payload: dict | None = None) -> FirewallRequest:
    return FirewallRequest(
        request_id="f2-test",
        message_type=message_type,
        issued_at_utc=NOW,
        payload={} if payload is None else payload,
    )


def test_policy_status_is_the_only_allowed_operation():
    result = authorize_request(request("POLICY_STATUS"), context=CONTEXT)
    assert result.allowed is True
    assert result.reason_code == "POLICY_STATUS_ONLY"


@pytest.mark.parametrize(
    ("operation", "reason"),
    [
        ("DEMO_EXECUTION", "DEMO_EXECUTION_DISABLED_IN_PHASE_5"),
        ("ORDER_CHECK", "DEMO_EXECUTION_DISABLED_IN_PHASE_5"),
        ("ORDER_SEND", "DEMO_EXECUTION_DISABLED_IN_PHASE_5"),
        ("ORDER_MODIFY", "DEMO_EXECUTION_DISABLED_IN_PHASE_5"),
        ("ORDER_CLOSE", "DEMO_EXECUTION_DISABLED_IN_PHASE_5"),
        ("LIVE_EXECUTION", "LIVE_MODE_PROHIBITED"),
        ("LIVE_ORDER_SEND", "LIVE_MODE_PROHIBITED"),
        ("ACCOUNT_FINANCIAL_READ", "A04_NOT_GRANTED"),
        ("READ_BALANCE", "A04_NOT_GRANTED"),
        ("READ_EQUITY", "A04_NOT_GRANTED"),
        ("READ_MARGIN", "A04_NOT_GRANTED"),
        ("READ_PROFIT", "A04_NOT_GRANTED"),
        ("UNKNOWN", "UNKNOWN_OR_UNAUTHORIZED_OPERATION"),
    ],
)
def test_privileged_unknown_and_forbidden_operations_fail_closed(operation, reason):
    result = authorize_request(request(operation), context=CONTEXT)
    assert result.allowed is False
    assert result.reason_code == reason


def test_status_request_rejects_payload():
    result = authorize_request(
        request("POLICY_STATUS", {"include_secrets": True}), context=CONTEXT
    )
    assert result == type(result)(False, "STATUS_PAYLOAD_NOT_ALLOWED")


@pytest.mark.parametrize(
    "context",
    [
        PolicyContext(phase=4, account_mode="DEMO"),
        PolicyContext(phase=6, account_mode="DEMO"),
        PolicyContext(phase=True, account_mode="DEMO"),
        PolicyContext(phase=5, account_mode="LIVE"),
        PolicyContext(phase=5, account_mode="CONTEST"),
        PolicyContext(phase=5, account_mode="demo"),
        PolicyContext(phase=5, account_mode=1),
    ],
)
def test_wrong_phase_or_account_scope_fails_closed(context):
    result = authorize_request(request("POLICY_STATUS"), context=context)
    assert result.allowed is False


def test_a09_phase12_scope_cannot_authorize_phase5_execution():
    # A-09 is not represented as a Phase 5 grant and cannot bypass this policy.
    result = authorize_request(request("DEMO_EXECUTION"), context=CONTEXT)
    assert result.allowed is False
    assert result.reason_code == "DEMO_EXECUTION_DISABLED_IN_PHASE_5"


def test_invalid_request_and_context_types_fail_closed():
    assert authorize_request(object(), context=CONTEXT).reason_code == "INVALID_REQUEST_TYPE"
    assert authorize_request(
        request("POLICY_STATUS"), context=object()
    ).reason_code == "INVALID_POLICY_CONTEXT"


def test_policy_is_pure_and_does_not_mutate_request():
    req = request("POLICY_STATUS")
    before = req.to_dict()
    authorize_request(req, context=CONTEXT)
    assert req.to_dict() == before
