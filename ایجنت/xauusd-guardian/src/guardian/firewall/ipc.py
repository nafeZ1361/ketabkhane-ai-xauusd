"""Authenticated, replay-resistant IPC primitives for the Phase 5 worker boundary.

F4: standard-library only. The transport is intentionally untrusted; every frame
is authenticated with a per-launch HMAC key, a session nonce, and a strictly
monotonic sequence number. A frame is accepted at most once.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any, Mapping

_MAX_FRAME = 64 * 1024
_MAX_CLOCK_SKEW = 30.0


class IPCError(ValueError):
    """Raised for malformed, unauthenticated, stale, or replayed IPC."""


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    except Exception as exc:
        raise IPCError("payload is not canonical JSON") from exc


def _require_bytes(name: str, value: Any, minimum: int) -> bytes:
    if type(value) is not bytes or len(value) < minimum:
        raise IPCError(f"{name} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class AuthenticatedSession:
    """One directional authenticated sequence state."""

    key: bytes
    session_nonce: bytes
    next_send_seq: int = 0
    next_recv_seq: int = 0

    def __post_init__(self) -> None:
        _require_bytes("key", self.key, 32)
        _require_bytes("session_nonce", self.session_nonce, 16)
        if type(self.next_send_seq) is not int or self.next_send_seq < 0:
            raise IPCError("invalid send sequence")
        if type(self.next_recv_seq) is not int or self.next_recv_seq < 0:
            raise IPCError("invalid receive sequence")

    def _mac(self, seq: int, issued_at: float, payload: bytes) -> bytes:
        material = (
            b"xauusd-guardian.firewall.v1\\0"
            + self.session_nonce
            + struct.pack("!Qd", seq, issued_at)
            + payload
        )
        return hmac.new(self.key, material, hashlib.sha256).digest()

    def encode(self, payload: Mapping[str, Any]) -> bytes:
        seq = self.next_send_seq
        issued_at = time.time()
        body = _canonical_json(payload)
        envelope = {
            "v": 1,
            "nonce": self.session_nonce.hex(),
            "seq": seq,
            "ts": issued_at,
            "payload": json.loads(body.decode("utf-8")),
            "mac": self._mac(seq, issued_at, body).hex(),
        }
        raw = _canonical_json(envelope)
        if len(raw) > _MAX_FRAME:
            raise IPCError("frame too large")
        object.__setattr__(self, "next_send_seq", seq + 1)
        return struct.pack("!I", len(raw)) + raw

    def decode(self, raw: bytes) -> Mapping[str, Any]:
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise IPCError("invalid IPC JSON") from exc
        if type(envelope) is not dict:
            raise IPCError("invalid IPC envelope")
        required = {"v", "nonce", "seq", "ts", "payload", "mac"}
        if set(envelope) != required:
            raise IPCError("unexpected IPC fields")
        if envelope["v"] != 1 or type(envelope["nonce"]) is not str:
            raise IPCError("unsupported IPC version")
        if envelope["nonce"] != self.session_nonce.hex():
            raise IPCError("session nonce mismatch")
        if type(envelope["seq"]) is not int or envelope["seq"] != self.next_recv_seq:
            raise IPCError("replayed or out-of-order IPC frame")
        if type(envelope["ts"]) not in (int, float):
            raise IPCError("invalid IPC timestamp")
        if abs(time.time() - float(envelope["ts"])) > _MAX_CLOCK_SKEW:
            raise IPCError("stale IPC frame")
        body = _canonical_json(envelope["payload"])
        expected = self._mac(envelope["seq"], float(envelope["ts"]), body)
        try:
            supplied = bytes.fromhex(envelope["mac"])
        except ValueError as exc:
            raise IPCError("invalid IPC MAC") from exc
        if not hmac.compare_digest(expected, supplied):
            raise IPCError("IPC authentication failed")
        object.__setattr__(self, "next_recv_seq", self.next_recv_seq + 1)
        return envelope["payload"]


def make_session() -> AuthenticatedSession:
    return AuthenticatedSession(
        key=secrets.token_bytes(32), session_nonce=secrets.token_bytes(16)
    )


def send_frame(sock: socket.socket, frame: bytes) -> None:
    try:
        sock.sendall(frame)
    except OSError as exc:
        raise IPCError("IPC send failed") from exc


def recv_frame(sock: socket.socket) -> bytes:
    try:
        header = _recv_exact(sock, 4)
        size = struct.unpack("!I", header)[0]
        if size <= 0 or size > _MAX_FRAME:
            raise IPCError("invalid IPC frame length")
        return _recv_exact(sock, size)
    except IPCError:
        raise
    except OSError as exc:
        raise IPCError("IPC receive failed") from exc


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise IPCError("IPC peer closed")
        data.extend(chunk)
    return bytes(data)
