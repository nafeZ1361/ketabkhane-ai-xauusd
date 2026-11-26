"""Fail-closed restricted worker and authenticated IPC endpoint for F4."""

from __future__ import annotations

import base64
import json
import os
import socket
import sys
from dataclasses import dataclass
from typing import Any, Mapping

from guardian.firewall.ipc import AuthenticatedSession, IPCError, recv_frame, send_frame
from guardian.firewall.worker_security import WorkerSecurityError, verify_current_worker_token


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    max_requests: int = 32

    def __post_init__(self) -> None:
        if type(self.max_requests) is not int or not 1 <= self.max_requests <= 1000:
            raise ValueError("max_requests must be an integer in [1,1000]")


def _read_bootstrap() -> Mapping[str, Any]:
    raw = sys.stdin.buffer.read(4096)
    if not raw or len(raw) > 4096:
        raise WorkerSecurityError("missing worker bootstrap")
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise WorkerSecurityError("invalid worker bootstrap") from exc
    if type(value) is not dict or set(value) != {"host", "port", "key", "nonce"}:
        raise WorkerSecurityError("unexpected worker bootstrap fields")
    return value


def run_worker() -> int:
    report = verify_current_worker_token()
    bootstrap = _read_bootstrap()
    host = bootstrap["host"]
    port = bootstrap["port"]
    if type(host) is not str or host != "127.0.0.1":
        raise WorkerSecurityError("worker endpoint must be loopback")
    if type(port) is not int or not 1 <= port <= 65535:
        raise WorkerSecurityError("invalid worker endpoint")
    try:
        key = base64.b64decode(bootstrap["key"], validate=True)
        nonce = bytes.fromhex(bootstrap["nonce"])
    except Exception as exc:
        raise WorkerSecurityError("invalid worker session material") from exc

    session = AuthenticatedSession(key=key, session_nonce=nonce)
    with socket.create_connection((host, port), timeout=5.0) as sock:
        send_frame(sock, session.encode({
            "type": "worker_hello",
            "pid": os.getpid(),
            "restricted": report.restricted,
            "integrity_rid": report.integrity_rid,
        }))
        frame = recv_frame(sock)
        command = session.decode(frame)
        if command.get("type") != "ready":
            raise IPCError("worker handshake rejected")
        for _ in range(32):
            frame = recv_frame(sock)
            message = session.decode(frame)
            if message.get("type") == "shutdown":
                send_frame(sock, session.encode({"type": "stopped"}))
                return 0
            # F4 worker has no execution capability. It echoes only a stable
            # liveness response; all future privileged commands are denied.
            send_frame(sock, session.encode({
                "type": "denied",
                "reason_code": "F4_WORKER_NO_EXECUTION_CAPABILITY",
            }))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run_worker())
    except Exception:
        # Security failures are intentionally silent and non-successful.
        raise SystemExit(70)
