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


@pytest.mark.parametrize("version", [True, 1.0, "1", 0, 2])
def test_direct_request_constructor_rejects_non_exact_schema_version(version):
    with pytest.raises(FirewallContractError):
        FirewallRequest("req", "TEST", T, {}, schema_version=version)


@pytest.mark.parametrize("version", [True, 1.0, "1", 0, 2])
def test_direct_response_constructor_rejects_non_exact_schema_version(version):
    with pytest.raises(FirewallContractError):
        FirewallResponse("req", "REJECTED", "NO_AUTH", T, schema_version=version)


class PermissiveProtocol:
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


@pytest.mark.parametrize("contract", ["request", "response"])
def test_direct_constructor_rejects_non_string_protocol(contract):
    with pytest.raises(FirewallContractError):
        if contract == "request":
            FirewallRequest("req", "TEST", T, {}, protocol=PermissiveProtocol())
        else:
            FirewallResponse("req", "REJECTED", "NO_AUTH", T, protocol=PermissiveProtocol())


def test_direct_request_constructor_rejects_non_mapping_payload():
    with pytest.raises(FirewallContractError):
        FirewallRequest("req", "TEST", T, [])


def test_payload_is_deeply_immutable_and_detached_from_input():
    source = {"nested": {"items": [1, {"ok": True}]}}
    request = FirewallRequest("req", "TEST", T, source)

    source["nested"]["items"][1]["ok"] = False
    assert request.to_dict()["payload"]["nested"]["items"][1]["ok"] is True

    with pytest.raises(TypeError):
        request.payload["new"] = "value"
    with pytest.raises(TypeError):
        request.payload["nested"]["new"] = "value"
    with pytest.raises(AttributeError):
        request.payload["nested"]["items"].append(2)


def test_to_dict_returns_independent_nested_payload_copy():
    request = FirewallRequest(
        "req", "TEST", T, {"nested": {"items": [1, {"ok": True}]}}
    )
    exported = request.to_dict()
    exported["payload"]["nested"]["items"][1]["ok"] = False
    exported["payload"]["nested"]["items"].append("changed")

    assert request.to_dict()["payload"] == {
        "nested": {"items": [1, {"ok": True}]}
    }


def test_to_dict_revalidates_payload_after_low_level_object_injection():
    request = FirewallRequest("req", "TEST", T, {"safe": True})
    object.__setattr__(request, "payload", {"injected": object()})

    with pytest.raises(FirewallContractError):
        request.to_dict()


def test_payload_nesting_limit_fails_with_contract_error():
    payload = {}
    cursor = payload
    for _ in range(65):
        child = {}
        cursor["nested"] = child
        cursor = child

    with pytest.raises(FirewallContractError, match="maximum JSON nesting depth"):
        FirewallRequest("req", "TEST", T, payload)


def test_cyclic_payload_fails_with_contract_error_not_recursion_error():
    payload = {}
    payload["self"] = payload

    with pytest.raises(FirewallContractError, match="maximum JSON nesting depth"):
        FirewallRequest("req", "TEST", T, payload)


def test_payload_exact_json_types_reject_container_subclasses():
    class StrangeList(list):
        pass

    with pytest.raises(FirewallContractError):
        FirewallRequest("req", "TEST", T, {"items": StrangeList([1])})
