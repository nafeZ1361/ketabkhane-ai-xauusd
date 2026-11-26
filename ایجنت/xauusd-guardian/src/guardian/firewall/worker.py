"""Fixed-purpose F4 worker loop. No broker, account, or execution capability."""

from __future__ import annotations

import os
import sys
from decimal import Decimal, InvalidOperation
from typing import Any

from guardian.domain.risk import RiskSpec
from guardian.firewall.ipc import (
    AuthenticatedCodec,
    IPCProtocolError,
    read_frame,
    write_frame,
)
from guardian.firewall.risk import revalidate_proposed_size

_SPEC_FIELDS = {
    "risk_fraction",
    "value_per_point_lot",
    "lot_step",
    "min_lot",
    "max_lot",
}


def _decimal(value: Any) -> Decimal:
    if type(value) is not str or not value or len(value) > 64:
        raise IPCProtocolError("INVALID_DECIMAL_TEXT")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise IPCProtocolError("INVALID_DECIMAL_TEXT") from exc
    if not result.is_finite():
        raise IPCProtocolError("NON_FINITE_DECIMAL")
    return result


def _risk(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"equity", "stop_points", "proposed_lots", "spec"}:
        raise IPCProtocolError("RISK_PAYLOAD_FIELDS_MISMATCH")
    raw_spec = payload["spec"]
    if type(raw_spec) is not dict or set(raw_spec) != _SPEC_FIELDS:
        raise IPCProtocolError("RISK_SPEC_FIELDS_MISMATCH")
    spec = RiskSpec(
        risk_fraction=_decimal(raw_spec["risk_fraction"]),
        value_per_point_lot=_decimal(raw_spec["value_per_point_lot"]),
        lot_step=_decimal(raw_spec["lot_step"]),
        min_lot=_decimal(raw_spec["min_lot"]),
        max_lot=_decimal(raw_spec["max_lot"]),
    )
    result = revalidate_proposed_size(
        _decimal(payload["equity"]),
        _decimal(payload["stop_points"]),
        _decimal(payload["proposed_lots"]),
        spec=spec,
    )
    return {
        "within_risk_limit": result.within_risk_limit,
        "reason_code": result.reason_code,
        "recomputed_max_lots": (
            str(result.recomputed_max_lots)
            if result.recomputed_max_lots is not None else None
        ),
    }


def _read_key(handle_value: int) -> bytes:
    if os.name != "nt":
        raise IPCProtocolError("UNSUPPORTED_PLATFORM")
    import msvcrt

    fd = msvcrt.open_osfhandle(handle_value, os.O_RDONLY | os.O_BINARY)
    try:
        chunks = bytearray()
        while len(chunks) < 32:
            part = os.read(fd, 32 - len(chunks))
            if not part:
                raise IPCProtocolError("SESSION_KEY_PIPE_TRUNCATED")
            chunks.extend(part)
        if os.read(fd, 1):
            raise IPCProtocolError("SESSION_KEY_PIPE_OVERSIZED")
        return bytearray(chunks)
    finally:
        os.close(fd)


def worker_main(key_handle: int, session_id: str) -> int:
    codec = None
    key = bytearray()
    try:
        key = _read_key(key_handle)
        codec = AuthenticatedCodec(
            key=key,
            session_id=session_id,
            send_direction="worker_to_parent",
            receive_direction="parent_to_worker",
        )
        for index in range(len(key)):
            key[index] = 0
        key.clear()
        write_frame(
            sys.stdout.buffer,
            codec.encode("READY", "startup", {"status": "READY"}),
        )
        while True:
            body = read_frame(sys.stdin.buffer)
            request = codec.decode(body)
            if request.message_type == "HEALTH_CHECK":
                if request.payload:
                    raise IPCProtocolError("HEALTH_CHECK_PAYLOAD_NOT_EMPTY")
                response_payload = {"status": "OK"}
            elif request.message_type == "RISK_REVALIDATE":
                response_payload = _risk(request.payload)
            else:
                raise IPCProtocolError("WORKER_OPERATION_NOT_ALLOWED")
            write_frame(
                sys.stdout.buffer,
                codec.encode("RESULT", request.correlation_id, response_payload),
            )
    except (IPCProtocolError, BrokenPipeError, OSError, ValueError):
        return 2
    except Exception:
        # Never serialize exception text, stack traces, payloads, or secrets to IPC.
        return 3
    finally:
        for index in range(len(key)):
            key[index] = 0
        key.clear()
        if codec is not None:
            codec.destroy()
