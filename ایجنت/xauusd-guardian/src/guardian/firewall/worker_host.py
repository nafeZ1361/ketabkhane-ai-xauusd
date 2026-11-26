"""Windows-only restricted worker host for F4.

No unrestricted subprocess fallback exists. Failure to create and verify the
restricted primary token or Job Object prevents worker startup.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import queue
import secrets
import subprocess
import sys
import tempfile
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any

from guardian.firewall.ipc import (
    AuthenticatedCodec,
    IPCProtocolError,
    read_frame,
    write_frame,
)


class WorkerHostError(RuntimeError):
    """The restricted worker could not be started or safely used."""


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", _SID_AND_ATTRIBUTES)]


class _LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", ctypes.c_longlong), ("Attributes", wintypes.DWORD)]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _configure_apis(kernel32: Any, advapi32: Any) -> None:
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.LPVOID]
    kernel32.LocalFree.restype = wintypes.LPVOID
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryInformationJobObject.restype = wintypes.BOOL
    kernel32.CreatePipe.argtypes = [ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(_SECURITY_ATTRIBUTES), wintypes.DWORD]
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID)]
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.SetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    advapi32.SetTokenInformation.restype = wintypes.BOOL
    advapi32.IsTokenRestricted.argtypes = [wintypes.HANDLE]
    advapi32.IsTokenRestricted.restype = wintypes.BOOL
    advapi32.GetLengthSid.argtypes = [wintypes.LPVOID]
    advapi32.GetLengthSid.restype = wintypes.DWORD
    advapi32.GetSidSubAuthorityCount.argtypes = [wintypes.LPVOID]
    advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi32.GetSidSubAuthority.argtypes = [wintypes.LPVOID, wintypes.DWORD]
    advapi32.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    advapi32.EqualSid.argtypes = [wintypes.LPVOID, wintypes.LPVOID]
    advapi32.EqualSid.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
        wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        ctypes.POINTER(_STARTUPINFOW), ctypes.POINTER(_PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL


def _win_error(operation: str) -> WorkerHostError:
    return WorkerHostError(f"{operation} failed (winerror={ctypes.get_last_error()})")


def _close_handle(kernel32: Any, handle: Any) -> None:
    if handle and handle != wintypes.HANDLE(-1).value:
        kernel32.CloseHandle(handle)


def _inspect_process_token(advapi32: Any, process: Any) -> dict[str, Any]:
    TOKEN_QUERY = 0x0008
    TokenGroups = 2
    TokenPrivileges = 3
    TokenIntegrityLevel = 25
    TokenElevation = 20
    SE_GROUP_USE_FOR_DENY_ONLY = 0x0010

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
        raise _win_error("OpenProcessToken(worker)")
    try:
        elevation = _TOKEN_ELEVATION()
        returned = wintypes.DWORD()
        if not advapi32.GetTokenInformation(
            token, TokenElevation, ctypes.byref(elevation),
            ctypes.sizeof(elevation), ctypes.byref(returned),
        ):
            raise _win_error("GetTokenInformation(worker elevation)")
        if elevation.TokenIsElevated != 0:
            raise WorkerHostError("WORKER_TOKEN_IS_ELEVATED")
        admin_sid = wintypes.LPVOID()
        if not advapi32.ConvertStringSidToSidW("S-1-5-32-544", ctypes.byref(admin_sid)):
            raise _win_error("ConvertStringSidToSidW(verify worker)")
        try:
            needed = wintypes.DWORD()
            advapi32.GetTokenInformation(token, TokenGroups, None, 0, ctypes.byref(needed))
            if not needed.value:
                raise _win_error("GetTokenInformation(worker groups size)")
            buffer = ctypes.create_string_buffer(needed.value)
            if not advapi32.GetTokenInformation(token, TokenGroups, buffer, needed.value, ctypes.byref(needed)):
                raise _win_error("GetTokenInformation(worker groups)")
            count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
            admin_present = False
            admin_deny_only = False
            group_offset = (ctypes.sizeof(wintypes.DWORD) + ctypes.sizeof(ctypes.c_void_p) - 1) & ~(ctypes.sizeof(ctypes.c_void_p) - 1)
            base = ctypes.addressof(buffer) + group_offset
            for index in range(count):
                item = ctypes.cast(
                    base + index * ctypes.sizeof(_SID_AND_ATTRIBUTES),
                    ctypes.POINTER(_SID_AND_ATTRIBUTES),
                ).contents
                if advapi32.EqualSid(item.Sid, admin_sid):
                    admin_present = True
                    admin_deny_only = bool(item.Attributes & SE_GROUP_USE_FOR_DENY_ONLY)
                    break
            if admin_present and not admin_deny_only:
                raise WorkerHostError("WORKER_ADMINISTRATORS_SID_NOT_DENY_ONLY")
        finally:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.LocalFree(admin_sid)


        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TokenPrivileges, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise _win_error("GetTokenInformation(worker privileges size)")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(token, TokenPrivileges, buffer, needed.value, ctypes.byref(needed)):
            raise _win_error("GetTokenInformation(worker privileges)")
        privilege_count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
        if privilege_count > 1:
            raise WorkerHostError("WORKER_TOKEN_PRIVILEGES_NOT_REDUCED")

        needed = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TokenIntegrityLevel, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise _win_error("GetTokenInformation(worker integrity size)")
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi32.GetTokenInformation(token, TokenIntegrityLevel, buffer, needed.value, ctypes.byref(needed)):
            raise _win_error("GetTokenInformation(worker integrity)")
        label = ctypes.cast(buffer, ctypes.POINTER(_TOKEN_MANDATORY_LABEL)).contents
        count_ptr = advapi32.GetSidSubAuthorityCount(label.Label.Sid)
        if not count_ptr or count_ptr.contents.value == 0:
            raise WorkerHostError("WORKER_TOKEN_INTEGRITY_INVALID")
        rid_ptr = advapi32.GetSidSubAuthority(label.Label.Sid, count_ptr.contents.value - 1)
        if not rid_ptr or rid_ptr.contents.value != 8192:
            raise WorkerHostError("WORKER_TOKEN_NOT_MEDIUM_INTEGRITY")

        return {
            "is_non_elevated": True,
            "administrators_sid_present": admin_present,
            "administrators_sid_deny_only": admin_deny_only if admin_present else None,
            "privilege_count": privilege_count,
            "integrity_rid": 8192,
        }
    finally:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle(token)


def _create_job(kernel32: Any) -> Any:
    JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise _win_error("CreateJobObjectW")
    limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_TIME | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    limits.BasicLimitInformation.PerProcessUserTimeLimit = 30 * 10_000_000
    limits.BasicLimitInformation.ActiveProcessLimit = 1
    limits.ProcessMemoryLimit = 128 * 1024 * 1024
    if not kernel32.SetInformationJobObject(
        job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
    ):
        _close_handle(kernel32, job)
        raise _win_error("SetInformationJobObject")
    verified = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    returned = wintypes.DWORD()
    if not kernel32.QueryInformationJobObject(
        job, 9, ctypes.byref(verified), ctypes.sizeof(verified), ctypes.byref(returned)
    ):
        _close_handle(kernel32, job)
        raise _win_error("QueryInformationJobObject")
    required_flags = (
        JOB_OBJECT_LIMIT_PROCESS_TIME | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    if (
        verified.BasicLimitInformation.LimitFlags & required_flags != required_flags
        or verified.BasicLimitInformation.ActiveProcessLimit != 1
        or verified.ProcessMemoryLimit != 128 * 1024 * 1024
        or verified.BasicLimitInformation.PerProcessUserTimeLimit != 30 * 10_000_000
    ):
        _close_handle(kernel32, job)
        raise WorkerHostError("JOB_OBJECT_LIMITS_NOT_VERIFIED")
    return job


def _pipe(kernel32: Any) -> tuple[Any, Any]:
    security = _SECURITY_ATTRIBUTES(
        ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True
    )
    read_handle = wintypes.HANDLE()
    write_handle = wintypes.HANDLE()
    if not kernel32.CreatePipe(
        ctypes.byref(read_handle), ctypes.byref(write_handle),
        ctypes.byref(security), 0,
    ):
        raise _win_error("CreatePipe")
    return read_handle, write_handle


def _non_inheritable(kernel32: Any, handle: Any) -> None:
    if not kernel32.SetHandleInformation(handle, 1, 0):
        raise _win_error("SetHandleInformation")


def parent_token_suitable() -> bool:
    """True only for a non-elevated, medium-integrity, privilege-reduced caller."""
    if os.name != "nt":
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        _configure_apis(kernel32, advapi32)
        _inspect_process_token(advapi32, kernel32.GetCurrentProcess())
        return True
    except Exception:
        return False


class RestrictedWorker:
    """Synchronous parent API for one authenticated, restricted worker session."""

    STARTUP_TIMEOUT_SECONDS = 8.0
    REQUEST_TIMEOUT_SECONDS = 3.0

    def __init__(self) -> None:
        self._kernel32 = None
        self._process = None
        self._thread = None
        self._job = None
        self._stdin = None
        self._stdout = None
        self._stderr = None
        self._reader_queue: queue.Queue[Any] = queue.Queue(maxsize=8)
        self._stderr_digest = None
        self._stderr_capture = bytearray()
        self._reader = None
        self._stderr_reader = None
        self._temp = None
        self._codec = None
        self._security_report = None
        self._job_limits_verified = False
        self._job_assigned = False
        self._closed = False
        self._poisoned = False

    @classmethod
    def launch(cls) -> "RestrictedWorker":
        if os.name != "nt":
            raise WorkerHostError("UNSUPPORTED_PLATFORM")
        host = cls()
        host._launch()
        return host

    def _launch(self) -> None:
        import msvcrt

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        _configure_apis(kernel32, advapi32)
        self._kernel32 = kernel32
        self._temp = tempfile.TemporaryDirectory(prefix="guardian-worker-")
        key = bytearray(secrets.token_bytes(32))
        key_buffer = None
        session_id = secrets.token_hex(32)
        self._codec = AuthenticatedCodec(
            key=key, session_id=session_id,
            send_direction="parent_to_worker",
            receive_direction="worker_to_parent",
        )

        child_stdin_read = child_stdin_write = None
        child_stdout_read = child_stdout_write = None
        child_stderr_read = child_stderr_write = None
        key_read = key_write = None
        process_info = _PROCESS_INFORMATION()
        try:
            _inspect_process_token(advapi32, kernel32.GetCurrentProcess())
            self._job = _create_job(kernel32)
            self._job_limits_verified = True

            child_stdin_read, child_stdin_write = _pipe(kernel32)
            child_stdout_read, child_stdout_write = _pipe(kernel32)
            child_stderr_read, child_stderr_write = _pipe(kernel32)
            key_read, key_write = _pipe(kernel32)

            for handle in (child_stdin_write, child_stdout_read, child_stderr_read, key_write):
                _non_inheritable(kernel32, handle)

            startup = _STARTUPINFOW()
            startup.cb = ctypes.sizeof(startup)
            startup.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
            startup.hStdInput = child_stdin_read
            startup.hStdOutput = child_stdout_write
            startup.hStdError = child_stderr_write

            project_root = Path(__file__).resolve().parents[3]
            worker_script = project_root / "scripts" / "firewall_worker.py"
            if not worker_script.is_file():
                raise WorkerHostError("FIXED_WORKER_ENTRYPOINT_MISSING")
            arguments = [
                sys.executable, "-I", "-S", str(worker_script),
                "--key-handle", str(int(key_read.value)),
                "--session-id", session_id,
            ]
            command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            temp_path = self._temp.name
            python_dir = str(Path(sys.executable).resolve().parent)
            safe_environment_names = {
                "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
                "ProgramData", "ProgramFiles", "ProgramFiles(x86)", "CommonProgramFiles",
                "CommonProgramFiles(x86)", "COMSPEC", "PATHEXT", "SYSTEMDRIVE",
                "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER", "NUMBER_OF_PROCESSORS",
            }
            environment_values = {
                key: value for key, value in os.environ.items()
                if key in safe_environment_names or key.startswith("=")
            }
            environment_values.update({
                "SystemRoot": system_root,
                "WINDIR": system_root,
                "TEMP": temp_path,
                "TMP": temp_path,
                "PATH": os.pathsep.join((
                    python_dir,
                    str(Path(python_dir) / "DLLs"),
                    str(Path(system_root) / "System32"),
                    system_root,
                )),
            })
            env_text = "\0".join(
                f"{key}={value}"
                for key, value in sorted(environment_values.items(), key=lambda item: item[0].casefold())
            ) + "\0\0"
            environment = ctypes.create_unicode_buffer(env_text)
            CREATE_SUSPENDED = 0x00000004
            CREATE_UNICODE_ENVIRONMENT = 0x00000400
            CREATE_NO_WINDOW = 0x08000000
            flags = CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW

            if not kernel32.CreateProcessW(
                sys.executable, command_line, None, None, True,
                flags, ctypes.cast(environment, wintypes.LPVOID),
                temp_path, ctypes.byref(startup), ctypes.byref(process_info),
            ):
                raise _win_error("CreateProcessW(non-elevated worker)")

            self._process = process_info.hProcess
            self._thread = process_info.hThread
            self._security_report = _inspect_process_token(advapi32, self._process)
            self._security_report["job_limits_verified"] = bool(self._job_limits_verified)
            self._security_report["job_assigned"] = bool(self._job_assigned)
            assigned = kernel32.AssignProcessToJobObject(self._job, self._process)
            if not assigned:
                raise _win_error("AssignProcessToJobObject")
            self._job_assigned = bool(assigned)
            self._security_report["job_assigned"] = self._job_assigned

            # The child is suspended, so the key pipe can be filled before Python runs.
            written = wintypes.DWORD()
            key_buffer = ctypes.create_string_buffer(bytes(key))
            if not kernel32.WriteFile(key_write, key_buffer, len(key), ctypes.byref(written), None):
                raise _win_error("WriteFile(session key)")
            if written.value != len(key):
                raise WorkerHostError("SESSION_KEY_PIPE_SHORT_WRITE")
            ctypes.memset(key_buffer, 0, len(key))
            for index in range(len(key)):
                key[index] = 0
            key.clear()
            _close_handle(kernel32, key_write)
            key_write = None

            # Parent closes its copies of every child-side handle before resume.
            for handle in (child_stdin_read, child_stdout_write, child_stderr_write, key_read):
                _close_handle(kernel32, handle)
            child_stdin_read = child_stdout_write = child_stderr_write = key_read = None

            if kernel32.ResumeThread(self._thread) == 0xFFFFFFFF:
                raise _win_error("ResumeThread")

            self._stdin = os.fdopen(
                msvcrt.open_osfhandle(int(child_stdin_write.value), os.O_WRONLY | os.O_BINARY),
                "wb", buffering=0,
            )
            child_stdin_write = None
            self._stdout = os.fdopen(
                msvcrt.open_osfhandle(int(child_stdout_read.value), os.O_RDONLY | os.O_BINARY),
                "rb", buffering=0,
            )
            child_stdout_read = None
            self._stderr = os.fdopen(
                msvcrt.open_osfhandle(int(child_stderr_read.value), os.O_RDONLY | os.O_BINARY),
                "rb", buffering=0,
            )
            child_stderr_read = None

            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            self._stderr_reader = threading.Thread(target=self._drain_stderr, daemon=True)
            self._stderr_reader.start()

            ready = self._next_message(self.STARTUP_TIMEOUT_SECONDS)
            if (
                ready.message_type != "READY"
                or ready.correlation_id != "startup"
                or ready.payload != {"status": "READY"}
            ):
                raise WorkerHostError("WORKER_STARTUP_HANDSHAKE_INVALID")
        except Exception:
            self.close(force=True)
            for handle in (
                child_stdin_read, child_stdin_write, child_stdout_read, child_stdout_write,
                child_stderr_read, child_stderr_write, key_read, key_write,
            ):
                _close_handle(kernel32, handle)
            raise
        finally:
            if key_buffer is not None:
                ctypes.memset(key_buffer, 0, 32)
            for index in range(len(key)):
                key[index] = 0
            key.clear()
            _close_handle(kernel32, self._thread)
            self._thread = None

    def _read_loop(self) -> None:
        try:
            while True:
                self._reader_queue.put(read_frame(self._stdout))
        except Exception as exc:
            try:
                self._reader_queue.put(exc, timeout=0.1)
            except queue.Full:
                pass

    def _drain_stderr(self) -> None:
        try:
            total = 0
            digest = hashlib.sha256()
            while True:
                chunk = self._stderr.read(1024)
                if not chunk:
                    self._stderr_digest = digest.hexdigest()
                    return
                total += len(chunk)
                if total <= 64 * 1024:
                    digest.update(chunk)
                if len(self._stderr_capture) < 4096:
                    self._stderr_capture.extend(chunk[: 4096 - len(self._stderr_capture)])
                # Drain to prevent pipe deadlock; retain only a bounded diagnostic tail.
        except Exception:
            return

    def _next_message(self, timeout: float):
        try:
            item = self._reader_queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise WorkerHostError("WORKER_RESPONSE_TIMEOUT") from exc
        if isinstance(item, Exception):
            exit_code = wintypes.DWORD(0xFFFFFFFF)
            if self._process is not None and self._kernel32.GetExitCodeProcess(self._process, ctypes.byref(exit_code)):
                code = exit_code.value
            else:
                code = None
            diagnostic = bytes(self._stderr_capture).decode("utf-8", errors="replace")
            diagnostic = diagnostic.replace(self._codec._session_id, "[SESSION]")
            raise WorkerHostError(f"WORKER_PIPE_CLOSED exit_code={code} stderr={diagnostic[-2000:]}") from item
        try:
            return self._codec.decode(item)
        except IPCProtocolError as exc:
            raise WorkerHostError("WORKER_AUTHENTICATION_OR_PROTOCOL_FAILURE") from exc

    @property
    def security_report(self) -> dict[str, Any]:
        if self._security_report is None:
            raise WorkerHostError("WORKER_SECURITY_NOT_VERIFIED")
        return dict(self._security_report)

    def request(self, message_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._closed or self._poisoned or self._stdin is None:
            raise WorkerHostError("WORKER_SESSION_NOT_AVAILABLE")
        if message_type not in ("HEALTH_CHECK", "RISK_REVALIDATE"):
            raise WorkerHostError("WORKER_OPERATION_NOT_ALLOWED")
        correlation_id = secrets.token_hex(16)
        try:
            body = self._codec.encode(message_type, correlation_id, payload)
            write_frame(self._stdin, body)
            response = self._next_message(self.REQUEST_TIMEOUT_SECONDS)
            if (
                response.message_type != "RESULT"
                or response.correlation_id != correlation_id
            ):
                raise WorkerHostError("WORKER_RESPONSE_CORRELATION_FAILURE")
            return response.payload
        except Exception:
            self._poisoned = True
            self.close(force=True)
            raise

    def close(self, *, force: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        kernel32 = self._kernel32
        if self._stdin is not None:
            try:
                self._stdin.close()
            except Exception:
                pass
        if self._process is not None and kernel32 is not None:
            WAIT_OBJECT_0 = 0
            WAIT_TIMEOUT = 0x00000102
            kernel32.WaitForSingleObject(self._process, 1000 if not force else 0)
            if force or kernel32.WaitForSingleObject(self._process, 0) == WAIT_TIMEOUT:
                kernel32.TerminateProcess(self._process, 2)
                kernel32.WaitForSingleObject(self._process, 5000)
        if self._job is not None and kernel32 is not None:
            _close_handle(kernel32, self._job)  # KILL_ON_JOB_CLOSE is the final containment.
            self._job = None
        for stream_name in ("_stdout", "_stderr"):
            stream = getattr(self, stream_name)
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
                setattr(self, stream_name, None)
        if self._process is not None and kernel32 is not None:
            _close_handle(kernel32, self._process)
            self._process = None
        if self._codec is not None:
            self._codec.destroy()
            self._codec = None
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None

    def __enter__(self) -> "RestrictedWorker":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close(force=exc is not None)
