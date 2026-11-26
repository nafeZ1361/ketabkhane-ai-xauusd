"""Anchored launcher for the F4 restricted worker."""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from guardian.firewall.ipc import AuthenticatedSession, IPCError, recv_frame, send_frame
from guardian.firewall.worker_security import WorkerSecurityError, create_restricted_worker


class WorkerLaunchError(RuntimeError):
    """Raised when a restricted worker cannot be established safely."""


@dataclass(frozen=True, slots=True)
class WorkerHandle:
    process: Any
    session: AuthenticatedSession
    socket: socket.socket
    pid: int


class RestrictedWorkerLauncher:
    """Launch exactly one restricted worker and verify its authenticated hello."""

    def __init__(self, *, python_executable: str | None = None) -> None:
        self.python_executable = python_executable or sys.executable

    def start(self, *, timeout: float = 5.0) -> WorkerHandle:
        if os.name != "nt":
            raise WorkerLaunchError("F4 requires a Windows restricted worker")
        if type(timeout) not in (int, float) or timeout <= 0 or timeout > 30:
            raise WorkerLaunchError("invalid startup timeout")

        session = AuthenticatedSession(
            key=os.urandom(32), session_nonce=os.urandom(16)
        )
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        except OSError:
            pass
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(timeout)
        port = server.getsockname()[1]

        bootstrap = json.dumps({
            "host": "127.0.0.1",
            "port": port,
            "key": base64.b64encode(session.key).decode("ascii"),
            "nonce": session.session_nonce.hex(),
        }, separators=(",", ":")).encode("utf-8")

        # Anonymous stdin pipe is used only for one-shot bootstrap material.
        read_fd, write_fd = os.pipe()
        try:
            os.set_inheritable(read_fd, True)
            os.set_inheritable(write_fd, False)
            command = subprocess.list2cmdline([
                self.python_executable, "-m", "guardian.firewall.worker"
            ])
            # The Windows API receives the inherited read handle explicitly;
            # no secret appears in argv or environment.
            pi = create_restricted_worker(command, read_fd)
            os.close(read_fd)
            read_fd = -1
            with os.fdopen(write_fd, "wb", closefd=True) as pipe:
                pipe.write(bootstrap)
                pipe.flush()
            conn, _ = server.accept()
            conn.settimeout(timeout)
            frame = recv_frame(conn)
            hello = session.decode(frame)
            if (
                hello.get("type") != "worker_hello"
                or hello.get("restricted") is not True
                or type(hello.get("integrity_rid")) is not int
                or hello.get("integrity_rid") >= 0x3000
                or hello.get("pid") != int(pi.dwProcessId)
            ):
                conn.close()
                raise WorkerLaunchError("worker security handshake failed")
            send_frame(conn, session.encode({"type": "ready"}))
            # The process handle is represented by a minimal subprocess-like
            # monitor. The launcher does not expose an execution API.
            return WorkerHandle(process=pi, session=session, socket=conn, pid=int(pi.dwProcessId))
        except Exception as exc:
            if read_fd >= 0:
                try:
                    os.close(read_fd)
                except OSError:
                    pass
            try:
                os.close(write_fd)
            except OSError:
                pass
            server.close()
            if isinstance(exc, WorkerLaunchError):
                raise
            raise WorkerLaunchError("restricted worker launch failed") from exc

    @staticmethod
    def shutdown(handle: WorkerHandle, *, timeout: float = 3.0) -> None:
        if type(handle) is not WorkerHandle:
            raise WorkerLaunchError("invalid worker handle")
        send_frame(handle.socket, handle.session.encode({"type": "shutdown"}))
        response = handle.session.decode(recv_frame(handle.socket))
        if response.get("type") != "stopped":
            raise WorkerLaunchError("worker did not confirm shutdown")
        handle.socket.close()
