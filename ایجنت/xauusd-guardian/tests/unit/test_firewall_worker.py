"""F4 fixed-purpose worker operation tests."""

from decimal import Decimal

import pytest

from guardian.firewall.ipc import IPCProtocolError
from guardian.firewall.worker import _risk


def valid_payload():
    return {
        "equity": "10000",
        "stop_points": "100",
        "proposed_lots": "0.50",
        "spec": {
            "risk_fraction": "0.01",
            "value_per_point_lot": "1",
            "lot_step": "0.01",
            "min_lot": "0.01",
            "max_lot": "100",
        },
    }


def test_worker_risk_operation_is_pure_and_returns_arithmetic_only():
    result = _risk(valid_payload())
    assert result == {
        "within_risk_limit": True,
        "reason_code": "RISK_WITHIN_LIMIT",
        "recomputed_max_lots": "1.00",
    }


def test_worker_denies_over_limit_risk_size():
    payload = valid_payload()
    payload["proposed_lots"] = "1.01"
    result = _risk(payload)
    assert result["within_risk_limit"] is False
    assert result["reason_code"] == "PROPOSED_SIZE_EXCEEDS_RECOMPUTED_MAXIMUM"


def test_worker_rejects_unknown_risk_payload_fields():
    payload = valid_payload()
    payload["order"] = {"side": "BUY"}
    with pytest.raises(IPCProtocolError, match="RISK_PAYLOAD_FIELDS_MISMATCH"):
        _risk(payload)


def test_worker_rejects_unknown_risk_spec_fields():
    payload = valid_payload()
    payload["spec"]["risk_override"] = "0.5"
    with pytest.raises(IPCProtocolError, match="RISK_SPEC_FIELDS_MISMATCH"):
        _risk(payload)


@pytest.mark.parametrize("value", [10000, 10000.0, None, "NaN", "Infinity", "x" * 65])
def test_worker_rejects_non_decimal_or_non_finite_numeric_text(value):
    payload = valid_payload()
    payload["equity"] = value
    with pytest.raises(IPCProtocolError):
        _risk(payload)


def test_worker_does_not_expose_order_or_account_operations():
    from guardian.firewall.ipc import AuthenticatedCodec

    codec = AuthenticatedCodec(
        key=b"x" * 32,
        session_id="cd" * 32,
        send_direction="parent_to_worker",
        receive_direction="worker_to_parent",
    )
    with pytest.raises(IPCProtocolError, match="MESSAGE_TYPE_NOT_ALLOWED"):
        codec.encode("ORDER_SEND", "order-1", {"symbol": "XAUUSD"})
