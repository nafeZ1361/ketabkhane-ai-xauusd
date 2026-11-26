"""Bounded, authenticated, replay-resistant IPC primitives for the F4 worker."""

from __future__ import annotations

import hashlib
import hmac
import json
import struct
from dataclasses import dataclass
from typing import Any, BinaryIO

IPC_PROTOCOL = "xauusd-guardian.ipc.v1"
IPC_VERSION = 1
MAX_FRAME_BYTES = 64 * 1024
MAX_JSON_DEPTH = 32
SESSION_ID_HEX_LENGTH = 64
KEY_BYTES = 32

_PARENT_MESSAGES = frozenset({"HEALTH_CHECK", "RISK_REVALIDATE"})
_WORKER_MESSAGES = frozenset({"READY", "RESULT", "ERROR"})


class IPCProtocolError(ValueError):
    """Malformed, unauthenticated, replayed, or out-of-scope IPC frame."""


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IPCProtocolError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise IPCProtocolError("NON_FINITE_JSON_NUMBER")


def _depth(value: Any, level: int = 0) -> None:
    if level > MAX_JSON_DEPTH:
        raise IPCProtocolError("JSON_NESTING_LIMIT")
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise IPCProtocolError("INVALID_JSON_KEY")
            _depth(item, level + 1)
    elif type(value) is list:
        for item in value:
            _depth(item, level + 1)
    elif value is None or type(value) in (str, bool, int):
        return
    elif type(value) is float:
        if not __import__("math").isfinite(value):
            raise IPCProtocolError("NON_FINITE_JSON_NUMBER")
    else:
        raise IPCProtocolError("UNSUPPORTED_JSON_VALUE")


def canonical_json(value: dict[str, Any]) -> bytes:
    if type(value) is not dict:
        raise IPCProtocolError("ENVELOPE_NOT_OBJECT")
    _depth(value)
    try:
        encoded = json.dumps(
            value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise IPCProtocolError("JSON_SERIALIZATION_FAILED") from exc
    if not encoded or len(encoded) > MAX_FRAME_BYTES:
        raise IPCProtocolError("FRAME_SIZE_LIMIT")
    return encoded


def _read_exact(stream: BinaryIO, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise IPCProtocolError("TRUNCATED_FRAME")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def write_frame(stream: BinaryIO, body: bytes) -> None:
    if type(body) is not bytes or not body or len(body) > MAX_FRAME_BYTES:
        raise IPCProtocolError("FRAME_SIZE_LIMIT")
    frame = struct.pack(">I", len(body)) + body
    view = memoryview(frame)
    while view:
        written = stream.write(view)
        if written is None:
            # Buffered streams may report None only when no progress is available.
            raise IPCProtocolError("FRAME_WRITE_FAILED")
        if written <= 0:
            raise IPCProtocolError("FRAME_WRITE_FAILED")
        view = view[written:]
    stream.flush()


def read_frame(stream: BinaryIO) -> bytes:
    header = _read_exact(stream, 4)
    (size,) = struct.unpack(">I", header)
    if size == 0 or size > MAX_FRAME_BYTES:
        raise IPCProtocolError("FRAME_SIZE_LIMIT")
    return _read_exact(stream, size)


def _parse_canonical(body: bytes) -> dict[str, Any]:
    if type(body) is not bytes or not body or len(body) > MAX_FRAME_BYTES:
        raise IPCProtocolError("FRAME_SIZE_LIMIT")
    try:
        text = body.decode("utf-8", errors="strict")
        value = json.loads(
            text, object_pairs_hook=_pairs_no_duplicates,
            parse_constant=_reject_constant,
        )
    except IPCProtocolError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise IPCProtocolError("INVALID_JSON_FRAME") from exc
    if type(value) is not dict:
        raise IPCProtocolError("ENVELOPE_NOT_OBJECT")
    _depth(value)
    if canonical_json(value) != body:
        raise IPCProtocolError("NON_CANONICAL_JSON")
    return value


@dataclass(frozen=True, slots=True)
class AuthenticatedMessage:
    direction: str
    sequence: int
    message_type: str
    correlation_id: str
    payload: dict[str, Any]


class AuthenticatedCodec:
    """One-direction-bound codec; exact sequence progression rejects replay/gaps."""

    def __init__(
        self, *, key: bytes, session_id: str, send_direction: str,
        receive_direction: str,
    ) -> None:
        if type(key) is not bytes or len(key) != KEY_BYTES:
            raise IPCProtocolError("INVALID_SESSION_KEY")
        if type(session_id) is not str or len(session_id) != SESSION_ID_HEX_LENGTH:
            raise IPCProtocolError("INVALID_SESSION_ID")
        try:
            bytes.fromhex(session_id)
        except ValueError as exc:
            raise IPCProtocolError("INVALID_SESSION_ID") from exc
        if send_direction not in ("parent_to_worker", "worker_to_parent"):
            raise IPCProtocolError("INVALID_DIRECTION")
        if receive_direction not in ("parent_to_worker", "worker_to_parent"):
            raise IPCProtocolError("INVALID_DIRECTION")
        if send_direction == receive_direction:
            raise IPCProtocolError("DIRECTION_COLLISION")
        self._key = key
        self._session_id = session_id
        self._send_direction = send_direction
        self._receive_direction = receive_direction
        self._send_sequence = 0
        self._receive_sequence = 0

    @property
    def send_sequence(self) -> int:
        return self._send_sequence

    @property
    def receive_sequence(self) -> int:
        return self._receive_sequence

    def _tag(self, direction: str, unsigned: dict[str, Any]) -> str:
        canonical = canonical_json(unsigned)
        digest = hmac.new(
            self._key,
            b"guardian-ipc-v1\x00" + direction.encode("ascii") + b"\x00" + canonical,
            hashlib.sha256,
        )
        return digest.hexdigest()

    def encode(self, message_type: str, correlation_id: str, payload: dict[str, Any]) -> bytes:
        if type(message_type) is not str or message_type not in _PARENT_MESSAGES if self._send_direction == "parent_to_worker" else type(message_type) is not str or message_type not in _WORKER_MESSAGES:
            raise IPCProtocolError("MESSAGE_TYPE_NOT_ALLOWED")
        if type(correlation_id) is not str or not correlation_id or len(correlation_id) > 128:
            raise IPCProtocolError("INVALID_CORRELATION_ID")
        if type(payload) is not dict:
            raise IPCProtocolError("PAYLOAD_NOT_OBJECT")
        _depth(payload)
        sequence = self._send_sequence + 1
        unsigned = {
            "protocol": IPC_PROTOCOL,
            "version": IPC_VERSION,
            "session_id": self._session_id,
            "sequence": sequence,
            "direction": self._send_direction,
            "message_type": message_type,
            "correlation_id": correlation_id,
            "payload": payload,
        }
        tag = self._tag(self._send_direction, unsigned)
        body = canonical_json({**unsigned, "tag": tag})
        self._send_sequence = sequence
        return body

    def decode(self, body: bytes) -> AuthenticatedMessage:
        envelope = _parse_canonical(body)
        expected_fields = {
            "protocol", "version", "session_id", "sequence", "direction",
            "message_type", "correlation_id", "payload", "tag",
        }
        if set(envelope) != expected_fields:
            raise IPCProtocolError("ENVELOPE_FIELDS_MISMATCH")
        if envelope["protocol"] != IPC_PROTOCOL or type(envelope["version"]) is not int or envelope["version"] != IPC_VERSION:
            raise IPCProtocolError("PROTOCOL_VERSION_MISMATCH")
        if envelope["session_id"] != self._session_id:
            raise IPCProtocolError("SESSION_MISMATCH")
        if envelope["direction"] != self._receive_direction:
            raise IPCProtocolError("DIRECTION_MISMATCH")
        sequence = envelope["sequence"]
        if type(sequence) is not int or sequence != self._receive_sequence + 1:
            raise IPCProtocolError("SEQUENCE_REPLAY_OR_GAP")
        message_type = envelope["message_type"]
        allowed = _WORKER_MESSAGES if self._receive_direction == "worker_to_parent" else _PARENT_MESSAGES
        if type(message_type) is not str or message_type not in allowed:
            raise IPCProtocolError("MESSAGE_TYPE_NOT_ALLOWED")
        correlation_id = envelope["correlation_id"]
        if type(correlation_id) is not str or not correlation_id or len(correlation_id) > 128:
            raise IPCProtocolError("INVALID_CORRELATION_ID")
        payload = envelope["payload"]
        if type(payload) is not dict:
            raise IPCProtocolError("PAYLOAD_NOT_OBJECT")
        tag = envelope["tag"]
        if type(tag) is not str or len(tag) != 64:
            raise IPCProtocolError("INVALID_AUTH_TAG")
        unsigned = {key: value for key, value in envelope.items() if key != "tag"}
        expected_tag = self._tag(self._receive_direction, unsigned)
        if not hmac.compare_digest(tag, expected_tag):
            raise IPCProtocolError("AUTHENTICATION_FAILED")
        self._receive_sequence = sequence
        return AuthenticatedMessage(
            direction=self._receive_direction,
            sequence=sequence,
            message_type=message_type,
            correlation_id=correlation_id,
            payload=payload,
        )
