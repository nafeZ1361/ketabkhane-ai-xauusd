"""F1 firewall contract tests: strict schema/version validation and fail-closed parsing."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from guardian.contracts.firewall import (
    FIREWALL_PROTOCOL,
    FIREWALL_SCHEMA_VERSION,
    FirewallContractError,
    FirewallRequest,
    FirewallResponse,
)

T = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)


def valid_request() -> dict:
    return {
        "schema_version": FIREWALL_SCHEMA_VERSION,
        "protocol": FIREWALL_PROTOCOL,
        "request_id": "req-001",
        "message_type": "TEST",
        "issued_at_utc": "2026-11-24T12:00:00Z",
        "payload": {"mode": "DEMO", "nested": {"ok": True}},
    }


def valid_response() -> dict:
    return {
        "schema_version": FIREWALL_SCHEMA_VERSION,
        "protocol": FIREWALL_PROTOCOL,
        "request_id": "req-001",
        "status": "REJECTED",
        "reason_code": "NOT_AUTHORIZED",
        "responded_at_utc": "2026-11-24T12:00:01Z",
    }


def test_request_round_trip_is_stable():
    request = FirewallRequest.from_dict(valid_request())
    assert FirewallRequest.from_dict(request.to_dict()) == request


def test_response_round_trip_is_stable():
    response = FirewallResponse.from_dict(valid_response())
    assert FirewallResponse.from_dict(response.to_dict()) == response


@pytest.mark.parametrize("field", ["request_id", "message_type", "protocol", "schema_version", "payload"])
def test_request_unknown_fields_are_rejected(field):
    data = valid_request()
    data[field + "_extra"] = "unexpected"
    with pytest.raises(FirewallContractError):
        FirewallRequest.from_dict(data)


def test_request_missing_field_is_rejected():
    data = valid_request()
    del data["payload"]
    with pytest.raises(FirewallContractError):
        FirewallRequest.from_dict(data)


@pytest.mark.parametrize("version", [0, 2, "1", True])
def test_request_wrong_schema_version_fails_closed(version):
    data = valid_request()
    data["schema_version"] = version
    with pytest.raises(FirewallContractError):
        FirewallRequest.from_dict(data)


def test_request_wrong_protocol_is_rejected():
    data = valid_request()
    data["protocol"] = "other.v1"
    with pytest.raises(FirewallContractError):
        FirewallRequest.from_dict(data)


def test_request_naive_timestamp_is_rejected():
    data = valid_request()
    data["issued_at_utc"] = "2026-11-24T12:00:00"
    with pytest.raises(FirewallContractError):
        FirewallRequest.from_dict(data)


def test_request_non_json_payload_is_rejected():
    data = valid_request()
    data["payload"] = {"bad": object()}
    with pytest.raises(FirewallContractError):
        FirewallRequest.from_dict(data)


def test_response_unknown_and_missing_fields_are_rejected():
    data = valid_response()
    data["unexpected"] = 1
    with pytest.raises(FirewallContractError):
        FirewallResponse.from_dict(data)

    data = valid_response()
    del data["reason_code"]
    with pytest.raises(FirewallContractError):
        FirewallResponse.from_dict(data)


def test_response_wrong_version_and_timestamp_are_rejected():
    data = valid_response()
    data["schema_version"] = 99
    with pytest.raises(FirewallContractError):
        FirewallResponse.from_dict(data)

    data = valid_response()
    data["responded_at_utc"] = "2026-11-24T12:00:01"
    with pytest.raises(FirewallContractError):
        FirewallResponse.from_dict(data)


def test_direct_contract_rejects_non_utc_and_non_mapping_payload():
    with pytest.raises(FirewallContractError):
        FirewallRequest(
            request_id="req",
            message_type="TEST",
            issued_at_utc=T.replace(tzinfo=None),
            payload={},
        )

    with pytest.raises(FirewallContractError):
        FirewallRequest(
            request_id="req",
            message_type="TEST",
            issued_at_utc=T,
            payload={"x": object()},
        )
