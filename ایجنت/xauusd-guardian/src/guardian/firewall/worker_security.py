"""Windows restricted-token security for the Phase 5 F4 worker boundary.

The launcher fails closed: if Windows cannot create and verify a restricted
worker token, no worker is started.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass


class WorkerSecurityError(RuntimeError):
    """Raised when a restricted worker cannot be established or verified."""


@dataclass(frozen=True, slots=True)
class WorkerTokenReport:
    restricted: bool
    integrity_rid: int
    elevation_type: int


if os.name != "nt":
    def verify_current_worker_token() -> WorkerTokenReport:
        raise WorkerSecurityError("F4 restricted worker requires Windows")

    def create_restricted_worker(*args, **kwargs):
        raise WorkerSecurityError("F4 restricted worker requires Windows")

    def is_launched_worker(launched_pid: int, reported_pid: int) -> bool:
        return launched_pid == reported_pid
else:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    TOKEN_QUERY = 0x0008
    TOKEN_DUPLICATE = 0x0002
    TOKEN_ASSIGN_PRIMARY = 0x0001
    TOKEN_ADJUST_DEFAULT = 0x0080
    DISABLE_MAX_PRIVILEGE = 0x1
    TokenElevationType = 18
    TokenHasRestrictions = 21
    TokenIntegrityLevel = 25
    STARTF_USESTDHANDLES = 0x00000100
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

    class TOKEN_MANDATORY_LABEL(ctypes.Structure):
        _fields_ = [("Label", SID_AND_ATTRIBUTES)]

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
            ("lpReserved2", wintypes.LPBYTE), ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
        ]

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.CreateRestrictedToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID,
        ctypes.POINTER(wintypes.HANDLE)
    ]
    advapi32.CreateRestrictedToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.CreateProcessAsUserW.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPWSTR,
        wintypes.LPVOID, wintypes.LPVOID, wintypes.BOOL, wintypes.DWORD,
        wintypes.LPVOID, wintypes.LPCWSTR, ctypes.POINTER(STARTUPINFO),
        ctypes.POINTER(PROCESS_INFORMATION)
    ]
    advapi32.CreateProcessAsUserW.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL

    def _raise_last_error(prefix: str) -> None:
        raise WorkerSecurityError(f"{prefix} (WinError {ctypes.get_last_error()})")

    def _open_current_token(access: int) -> wintypes.HANDLE:
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), access, ctypes.byref(token)
        ):
            _raise_last_error("OpenProcessToken failed")
        return token

    def _query_dword(token: wintypes.HANDLE, info_class: int) -> int:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, info_class, None, 0, ctypes.byref(size))
        if not size.value:
            _raise_last_error("GetTokenInformation size query failed")
        buf = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(
            token, info_class, buf, size, ctypes.byref(size)
        ):
            _raise_last_error("GetTokenInformation failed")
        return ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value

    def _integrity_rid(token: wintypes.HANDLE) -> int:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TokenIntegrityLevel, None, 0, ctypes.byref(size))
        if not size.value:
            _raise_last_error("TokenIntegrityLevel size query failed")
        buf = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(
            token, TokenIntegrityLevel, buf, size, ctypes.byref(size)
        ):
            _raise_last_error("TokenIntegrityLevel query failed")
        label = ctypes.cast(buf, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
        sid = ctypes.cast(label.Label.Sid, ctypes.POINTER(ctypes.c_ubyte))
        count = sid[1]
        if count < 1:
            raise WorkerSecurityError("invalid integrity SID")
        address = ctypes.addressof(sid.contents) + 8 + 4 * (count - 1)
        return ctypes.cast(address, ctypes.POINTER(wintypes.DWORD)).contents.value

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL

    def _parent_pid(pid: int) -> int | None:
        """Return the OS-recorded parent PID, or None if it cannot be read."""
        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snapshot or snapshot == INVALID_HANDLE_VALUE:
            return None
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
                return None
            while True:
                if int(entry.th32ProcessID) == pid:
                    return int(entry.th32ParentProcessID)
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    return None
        finally:
            kernel32.CloseHandle(snapshot)

    def is_launched_worker(launched_pid: int, reported_pid: int) -> bool:
        """True when the reporter is the launched process or its direct child.

        The Windows venv ``python.exe`` is a redirector: CreateProcessAsUserW
        creates the redirector, and the interpreter that actually runs the
        worker is its direct child. Only that exact relationship is accepted.
        """
        if reported_pid == launched_pid:
            return True
        return _parent_pid(reported_pid) == launched_pid

    def verify_current_worker_token() -> WorkerTokenReport:
        token = _open_current_token(TOKEN_QUERY)
        try:
            restricted = bool(_query_dword(token, TokenHasRestrictions))
            elevation = _query_dword(token, TokenElevationType)
            integrity = _integrity_rid(token)
            # F4 accepts only an actually restricted token. UAC elevation type
            # is deliberately not used as the security predicate.
            if not restricted:
                raise WorkerSecurityError(
                    f"worker token is unrestricted: integrity_rid={integrity}, "
                    f"elevation_type={elevation}"
                )
            return WorkerTokenReport(restricted, integrity, elevation)
        finally:
            kernel32.CloseHandle(token)

    def create_restricted_worker(
        *,
        application_name: str,
        command_line: str,
        stdin_handle: int,
        working_directory: str,
    ) -> PROCESS_INFORMATION:
        token = _open_current_token(
            TOKEN_QUERY | TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT
        )
        restricted = wintypes.HANDLE()
        if not advapi32.CreateRestrictedToken(
            token, DISABLE_MAX_PRIVILEGE, 0, None, 0, None, 0, None,
            ctypes.byref(restricted)
        ):
            kernel32.CloseHandle(token)
            _raise_last_error("CreateRestrictedToken failed")
        try:
            si = STARTUPINFO()
            si.cb = ctypes.sizeof(STARTUPINFO)
            si.dwFlags = STARTF_USESTDHANDLES
            si.hStdInput = wintypes.HANDLE(stdin_handle)
            pi = PROCESS_INFORMATION()
            if not advapi32.CreateProcessAsUserW(
                restricted,
                application_name,
                ctypes.create_unicode_buffer(command_line),
                None,
                None,
                True,
                0,
                None,
                working_directory,
                ctypes.byref(si),
                ctypes.byref(pi),
            ):
                _raise_last_error("CreateProcessAsUserW failed for restricted worker")
            return pi
        finally:
            kernel32.CloseHandle(restricted)
            kernel32.CloseHandle(token)

    def wait_process(handle: PROCESS_INFORMATION, timeout_ms: int) -> bool:
        result = kernel32.WaitForSingleObject(handle.hProcess, timeout_ms)
        if result == WAIT_OBJECT_0:
            return True
        if result == WAIT_TIMEOUT:
            return False
        _raise_last_error("WaitForSingleObject failed")

    def exit_code(handle: PROCESS_INFORMATION) -> int:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle.hProcess, ctypes.byref(code)):
            _raise_last_error("GetExitCodeProcess failed")
        return int(code.value)

    def terminate_process(handle: PROCESS_INFORMATION) -> None:
        if not kernel32.TerminateProcess(handle.hProcess, 70):
            _raise_last_error("TerminateProcess failed")

    def close_process_handles(handle: PROCESS_INFORMATION) -> None:
        kernel32.CloseHandle(handle.hThread)
        kernel32.CloseHandle(handle.hProcess)
