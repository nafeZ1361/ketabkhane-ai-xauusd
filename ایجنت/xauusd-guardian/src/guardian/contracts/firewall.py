"""Strict typed contracts for the Phase 5 firewall boundary.

F1 only: contracts and schema/version validation. This module performs no I/O,
no MT5 access, no authorization, and no order construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

FIREWALL_SCHEMA_VERSION = 1
FIREWALL_PROTOCOL = "xauusd-guardian.firewall.v1"
MAX_JSON_NESTING_DEPTH = 64

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class FirewallContractError(ValueError):
    """Raised when a firewall contract is malformed or unsafe."""


def _require_exact_keys(data: Mapping[str, Any], expected: set[str]) -> None:
    actual = set(data)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise FirewallContractError(f"missing fields: {sorted(missing)}")
    if unknown:
        raise FirewallContractError(f"unknown fields: {sorted(unknown)}")


def _require_nonempty_str(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FirewallContractError(f"{name} must be a non-empty string")
    return value


def _require_schema_protocol(schema_version: Any, protocol: Any) -> None:
    # Exact checks are intentional: bool is an int subclass and 1.0 == 1.
    if type(schema_version) is not int or schema_version != FIREWALL_SCHEMA_VERSION:
        raise FirewallContractError(f"unsupported schema_version: {schema_version!r}")
    if type(protocol) is not str or protocol != FIREWALL_PROTOCOL:
        raise FirewallContractError(f"unsupported protocol: {protocol!r}")


def _require_utc_datetime(name: str, value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise FirewallContractError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise FirewallContractError(f"{name} must be timezone-aware")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise FirewallContractError(f"{name} must use UTC")
    return value


def _validate_json(value: Any, path: str = "payload", depth: int = 0) -> JsonValue:
    if depth > MAX_JSON_NESTING_DEPTH:
        raise FirewallContractError(
            f"{path} exceeds maximum JSON nesting depth "
            f"({MAX_JSON_NESTING_DEPTH})"
        )
    value_type = type(value)
    if value is None or value_type in (str, bool, int):
        return value
    if value_type is float:
        if value != value or value in (float("inf"), float("-inf")):
            raise FirewallContractError(f"{path} contains non-finite float")
        return value
    if value_type is list:
        return [
            _validate_json(item, f"{path}[{i}]", depth + 1)
            for i, item in enumerate(value)
        ]
    if value_type is dict:
        result: dict[str, JsonValue] = {}
        for key, item in value.items():
            if type(key) is not str or not key:
                raise FirewallContractError(f"{path} contains an invalid object key")
            result[key] = _validate_json(item, f"{path}.{key}", depth + 1)
        return result
    raise FirewallContractError(
        f"{path} contains unsupported type: {value_type.__name__}"
    )


def _freeze_json(value: JsonValue) -> Any:
    """Return a recursively immutable representation of validated JSON."""
    if type(value) is dict:
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: Any) -> JsonValue:
    """Return a fresh, mutable JSON-compatible copy for serialization."""
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw_json(item) for item in value]
    return value


def _validated_payload(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise FirewallContractError("payload must be a mapping")
    try:
        validated = _validate_json(dict(payload))
    except RecursionError as exc:
        raise FirewallContractError("payload exceeds safe nesting depth") from exc
    if type(validated) is not dict:
        raise FirewallContractError("payload must be a JSON object")
    return _freeze_json(validated)


@dataclass(frozen=True, slots=True)
class FirewallRequest:
    """Inbound typed message accepted by the future firewall boundary.

    F1 deliberately does not authorize execution and contains no order API.
    """

    request_id: str
    message_type: str
    issued_at_utc: datetime
    payload: Mapping[str, JsonValue]
    schema_version: int = FIREWALL_SCHEMA_VERSION
    protocol: str = FIREWALL_PROTOCOL

    def __post_init__(self) -> None:
        _require_schema_protocol(self.schema_version, self.protocol)
        _require_nonempty_str("request_id", self.request_id)
        _require_nonempty_str("message_type", self.message_type)
        _require_utc_datetime("issued_at_utc", self.issued_at_utc)
        object.__setattr__(self, "payload", _validated_payload(self.payload))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "protocol": self.protocol,
            "request_id": self.request_id,
            "message_type": self.message_type,
            "issued_at_utc": self.issued_at_utc.isoformat().replace("+00:00", "Z"),
            "payload": _thaw_json(self.payload),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FirewallRequest":
        if not isinstance(data, Mapping):
            raise FirewallContractError("request must be a mapping")
        expected = {
            "schema_version",
            "protocol",
            "request_id",
            "message_type",
            "issued_at_utc",
            "payload",
        }
        _require_exact_keys(data, expected)
        _require_schema_protocol(data["schema_version"], data["protocol"])
        request_id = _require_nonempty_str("request_id", data["request_id"])
        message_type = _require_nonempty_str("message_type", data["message_type"])
        issued = data["issued_at_utc"]
        if not isinstance(issued, str):
            raise FirewallContractError("issued_at_utc must be an ISO-8601 string")
        try:
            parsed = datetime.fromisoformat(issued.replace("Z", "+00:00"))
        except ValueError as exc:
            raise FirewallContractError("invalid issued_at_utc") from exc
        return cls(
            request_id=request_id,
            message_type=message_type,
            issued_at_utc=parsed,
            payload=data["payload"],
            schema_version=data["schema_version"],
            protocol=data["protocol"],
        )


@dataclass(frozen=True, slots=True)
class FirewallResponse:
    """Typed firewall result contract; it is not an execution authorization."""

    request_id: str
    status: str
    reason_code: str
    responded_at_utc: datetime
    schema_version: int = FIREWALL_SCHEMA_VERSION
    protocol: str = FIREWALL_PROTOCOL

    def __post_init__(self) -> None:
        _require_schema_protocol(self.schema_version, self.protocol)
        for name, value in (
            ("request_id", self.request_id),
            ("status", self.status),
            ("reason_code", self.reason_code),
        ):
            _require_nonempty_str(name, value)
        _require_utc_datetime("responded_at_utc", self.responded_at_utc)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "protocol": self.protocol,
            "request_id": self.request_id,
            "status": self.status,
            "reason_code": self.reason_code,
            "responded_at_utc": self.responded_at_utc.isoformat().replace("+00:00", "Z"),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FirewallResponse":
        if not isinstance(data, Mapping):
            raise FirewallContractError("response must be a mapping")
        expected = {
            "schema_version",
            "protocol",
            "request_id",
            "status",
            "reason_code",
            "responded_at_utc",
        }
        _require_exact_keys(data, expected)
        _require_schema_protocol(data["schema_version"], data["protocol"])
        values = {
            "request_id": _require_nonempty_str("request_id", data["request_id"]),
            "status": _require_nonempty_str("status", data["status"]),
            "reason_code": _require_nonempty_str("reason_code", data["reason_code"]),
            "protocol": data["protocol"],
            "schema_version": data["schema_version"],
        }
        timestamp = data["responded_at_utc"]
        if not isinstance(timestamp, str):
            raise FirewallContractError("responded_at_utc must be an ISO-8601 string")
        try:
            values["responded_at_utc"] = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise FirewallContractError("invalid responded_at_utc") from exc
        return cls(**values)
