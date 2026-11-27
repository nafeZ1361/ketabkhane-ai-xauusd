"""Anchored launcher for the F4 restricted worker."""

from __future__ import annotations

import base64
import json
import os
import socket
import sys
from dataclasses import dataclass
from typing import Any

from guardian.firewall.ipc import AuthenticatedSession, IPCError, recv_frame, send_frame
from guardian.firewall.worker_security import (
    PROCESS_INFORMATION,
    WorkerSecurityError,
    close_process_handles,
    create_restricted_worker,
    exit_code,
    is_launched_worker,
    terminate_process,
    wait_process,
)


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
        self.python_executable = os.path.abspath(python_executable or sys.executable)
        # Anchor the worker's module search root to this package's own source
        # directory so `-m guardian.firewall.worker` resolves regardless of the
        # caller's working directory. Never inherit an arbitrary cwd here.
        self.worker_module_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    def start(self, *, timeout: float = 5.0) -> WorkerHandle:
        if os.name != "nt":
            raise WorkerLaunchError("F4 requires a Windows restricted worker")
        if not os.path.isfile(self.python_executable):
            raise WorkerLaunchError("anchored Python executable does not exist")
        if not os.path.isfile(
            os.path.join(
                self.worker_module_root, "guardian", "firewall", "worker.py"
            )
        ):
            raise WorkerLaunchError("anchored worker module does not exist")
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

        bootstrap = json.dumps(
            {
                "host": "127.0.0.1",
                "port": port,
                "key": base64.b64encode(session.key).decode("ascii"),
                "nonce": session.session_nonce.hex(),
            },
            separators=(",", ":"),
        ).encode("utf-8")

        read_fd, write_fd = os.pipe()
        pi: PROCESS_INFORMATION | None = None
        conn: socket.socket | None = None
        try:
            os.set_inheritable(read_fd, True)
            os.set_inheritable(write_fd, False)
            # CreateProcessAsUserW requires a kernel HANDLE, but os.pipe()
            # returns CRT descriptors. Passing the descriptor makes the child
            # start with an unusable stdin, so the bootstrap is never read and
            # the worker dies before connecting. Convert explicitly.
            import msvcrt

            stdin_handle = msvcrt.get_osfhandle(read_fd)
            command_line = f'"{self.python_executable}" -m guardian.firewall.worker'
            pi = create_restricted_worker(
                application_name=self.python_executable,
                command_line=command_line,
                stdin_handle=stdin_handle,
                working_directory=self.worker_module_root,
            )
            os.close(read_fd)
            read_fd = -1
            with os.fdopen(write_fd, "wb", closefd=True) as pipe:
                pipe.write(bootstrap)
                pipe.flush()
            conn, _ = server.accept()
            conn.settimeout(timeout)
            hello = session.decode(recv_frame(conn))
            worker_pid = hello.get("pid")
            if (
                hello.get("type") != "worker_hello"
                or hello.get("restricted") is not True
                or type(hello.get("integrity_rid")) is not int
                or type(worker_pid) is not int
                or not is_launched_worker(int(pi.dwProcessId), worker_pid)
            ):
                raise WorkerLaunchError("worker security handshake failed")
            send_frame(conn, session.encode({"type": "ready"}))
            server.close()
            return WorkerHandle(
                process=pi, session=session, socket=conn, pid=int(pi.dwProcessId)
            )
        except Exception as exc:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass
            if read_fd >= 0:
                try:
                    os.close(read_fd)
                except OSError:
                    pass
            try:
                os.close(write_fd)
            except OSError:
                pass
            if pi is not None:
                try:
                    if not wait_process(pi, 0):
                        terminate_process(pi)
                        wait_process(pi, 3000)
                finally:
                    close_process_handles(pi)
            server.close()
            if isinstance(exc, WorkerLaunchError):
                raise
            raise WorkerLaunchError("restricted worker launch failed") from exc

    @staticmethod
    def shutdown(handle: WorkerHandle, *, timeout: float = 3.0) -> None:
        if type(handle) is not WorkerHandle:
            raise WorkerLaunchError("invalid worker handle")
        try:
            send_frame(handle.socket, handle.session.encode({"type": "shutdown"}))
            response = handle.session.decode(recv_frame(handle.socket))
            if response.get("type") != "stopped":
                raise WorkerLaunchError("worker did not confirm shutdown")
            if not wait_process(handle.process, int(timeout * 1000)):
                terminate_process(handle.process)
                if not wait_process(handle.process, 3000):
                    raise WorkerLaunchError("worker failed to terminate")
            if exit_code(handle.process) != 0:
                raise WorkerLaunchError("worker exited with failure")
        finally:
            try:
                handle.socket.close()
            finally:
                close_process_handles(handle.process)
