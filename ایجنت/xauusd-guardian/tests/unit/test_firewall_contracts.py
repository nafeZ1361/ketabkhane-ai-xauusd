"""F1 firewall contract tests: strict schema/version validation and fail-closed parsing."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone, tzinfo

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


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 1.0),
        ("schema_version", 2),
        ("protocol", PermissiveProtocol()),
        ("request_id", ""),
        ("message_type", ""),
        ("issued_at_utc", object()),
        ("issued_at_utc", datetime(2026, 11, 24, 12, 0)),
    ],
)
def test_request_to_dict_revalidates_every_field_after_low_level_injection(field, value):
    request = FirewallRequest("req", "TEST", T, {"safe": True})
    object.__setattr__(request, field, value)

    with pytest.raises(FirewallContractError):
        request.to_dict()


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 1.0),
        ("schema_version", 2),
        ("protocol", PermissiveProtocol()),
        ("request_id", ""),
        ("status", ""),
        ("reason_code", ""),
        ("responded_at_utc", object()),
        ("responded_at_utc", datetime(2026, 11, 24, 12, 0)),
    ],
)
def test_response_to_dict_revalidates_every_field_after_low_level_injection(field, value):
    response = FirewallResponse("req", "REJECTED", "NO_AUTH", T)
    object.__setattr__(response, field, value)

    with pytest.raises(FirewallContractError):
        response.to_dict()


class ExplodingMapping(Mapping):
    """Mapping whose read operations fail with a non-contract exception."""

    def __getitem__(self, key):
        raise RuntimeError("hostile mapping access")

    def __iter__(self):
        return iter(("payload",))

    def __len__(self):
        return 1


class OffsetChangesAfterValidation(tzinfo):
    """Return UTC during validation, then attempt to change the serialized offset."""

    def __init__(self):
        self.calls = 0

    def utcoffset(self, dt):
        self.calls += 1
        return timedelta(0) if self.calls <= 4 else timedelta(hours=1)

    def dst(self, dt):
        return timedelta(0)


def test_request_freezes_untrusted_timezone_before_serialization():
    changing_tz = OffsetChangesAfterValidation()
    request = FirewallRequest(
        "req", "TEST", datetime(2026, 11, 24, 12, 0, tzinfo=changing_tz), {}
    )

    assert changing_tz.calls == 1
    assert request.issued_at_utc.tzinfo is timezone.utc
    assert request.to_dict()["issued_at_utc"] == "2026-11-24T12:00:00Z"
    assert changing_tz.calls == 1


def test_response_freezes_untrusted_timezone_before_serialization():
    changing_tz = OffsetChangesAfterValidation()
    response = FirewallResponse(
        "req", "REJECTED", "NO_AUTH",
        datetime(2026, 11, 24, 12, 0, tzinfo=changing_tz),
    )

    assert changing_tz.calls == 1
    assert response.responded_at_utc.tzinfo is timezone.utc
    assert response.to_dict()["responded_at_utc"] == "2026-11-24T12:00:00Z"
    assert changing_tz.calls == 1


def test_request_constructor_wraps_hostile_payload_mapping_exception():
    with pytest.raises(FirewallContractError, match="cannot be read safely"):
        FirewallRequest("req", "TEST", T, ExplodingMapping())


@pytest.mark.parametrize("contract", ["request", "response"])
def test_from_dict_wraps_hostile_top_level_mapping_exception(contract):
    with pytest.raises(FirewallContractError, match="cannot be read safely"):
        if contract == "request":
            FirewallRequest.from_dict(ExplodingMapping())
        else:
            FirewallResponse.from_dict(ExplodingMapping())


def test_request_rejects_non_string_field_names_before_sorting():
    data = valid_request()
    data["unexpected"] = "value"
    data[1] = "non-string key"

    with pytest.raises(FirewallContractError, match="field names must be strings"):
        FirewallRequest.from_dict(data)


def test_to_dict_wraps_hostile_payload_mapping_after_low_level_injection():
    request = FirewallRequest("req", "TEST", T, {"safe": True})
    object.__setattr__(request, "payload", ExplodingMapping())

    with pytest.raises(FirewallContractError):
        request.to_dict()


def test_serialization_revalidates_and_freezes_injected_changing_timezone():
    changing_tz = OffsetChangesAfterValidation()
    request = FirewallRequest("req", "TEST", T, {})
    injected = datetime(2026, 11, 24, 12, 0, tzinfo=changing_tz)
    object.__setattr__(request, "issued_at_utc", injected)

    assert request.to_dict()["issued_at_utc"] == "2026-11-24T12:00:00Z"
    assert changing_tz.calls == 1

    changing_tz = OffsetChangesAfterValidation()
    response = FirewallResponse("req", "REJECTED", "NO_AUTH", T)
    injected = datetime(2026, 11, 24, 12, 0, tzinfo=changing_tz)
    object.__setattr__(response, "responded_at_utc", injected)

    assert response.to_dict()["responded_at_utc"] == "2026-11-24T12:00:00Z"
    assert changing_tz.calls == 1
