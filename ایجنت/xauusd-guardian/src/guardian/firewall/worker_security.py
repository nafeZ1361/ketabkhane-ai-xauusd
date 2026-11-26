"""Windows worker-token security for Phase 5 F4.

The launcher never falls back to an unrestricted worker. On unsupported
platforms or when the Windows restricted-token APIs fail, launch is denied.
"""

from __future__ import annotations

import ctypes
import os
import sys
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
else:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    TOKEN_QUERY = 0x0008
    TOKEN_DUPLICATE = 0x0002
    TOKEN_ASSIGN_PRIMARY = 0x0001
    TOKEN_ADJUST_DEFAULT = 0x0080
    TOKEN_ADJUST_SESSIONID = 0x0100
    DISABLE_MAX_PRIVILEGE = 0x1
    SecurityImpersonation = 2
    TokenPrimary = 1
    TokenElevationType = 18
    TokenIntegrityLevel = 25
    TokenHasRestrictions = 21

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

    class TOKEN_MANDATORY_LABEL(ctypes.Structure):
        _fields_ = [("Label", SID_AND_ATTRIBUTES)]

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", wintypes.LPVOID),
            ("bInheritHandle", wintypes.BOOL),
        ]

    class STARTUPINFO(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", wintypes.LPBYTE),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
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
        ctypes.POINTER(SECURITY_ATTRIBUTES), ctypes.POINTER(SECURITY_ATTRIBUTES),
        wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFO), ctypes.POINTER(PROCESS_INFORMATION)
    ]
    advapi32.CreateProcessAsUserW.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetLastError.restype = wintypes.DWORD

    def _raise_last_error(prefix: str) -> None:
        err = ctypes.get_last_error()
        raise WorkerSecurityError(f"{prefix} (WinError {err})")

    def _open_current_token(access: int) -> wintypes.HANDLE:
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), access, ctypes.byref(token)):
            _raise_last_error("OpenProcessToken failed")
        return token

    def _query_dword(token: wintypes.HANDLE, info_class: int) -> int:
        size = wintypes.DWORD()
        if advapi32.GetTokenInformation(token, info_class, None, 0, ctypes.byref(size)):
            raise WorkerSecurityError("unexpected token query success")
        buf = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, info_class, buf, size, ctypes.byref(size)):
            _raise_last_error("GetTokenInformation failed")
        return ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD)).contents.value

    def _integrity_rid(token: wintypes.HANDLE) -> int:
        size = wintypes.DWORD()
        advapi32.GetTokenInformation(token, TokenIntegrityLevel, None, 0, ctypes.byref(size))
        if not size.value:
            _raise_last_error("TokenIntegrityLevel size query failed")
        buf = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(token, TokenIntegrityLevel, buf, size, ctypes.byref(size)):
            _raise_last_error("TokenIntegrityLevel query failed")
        label = ctypes.cast(buf, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
        # Integrity SID is S-1-16-RID; sub-authority count is byte 1 and RID is
        # the final DWORD at the SID's sub-authority array.
        sid = ctypes.cast(label.Label.Sid, ctypes.POINTER(ctypes.c_ubyte))
        count = sid[1]
        if count < 1:
            raise WorkerSecurityError("invalid integrity SID")
        rid_ptr = ctypes.cast(ctypes.addressof(sid.contents) + 8 + 4 * (count - 1),
                              ctypes.POINTER(wintypes.DWORD))
        return rid_ptr.contents.value

    def verify_current_worker_token() -> WorkerTokenReport:
        token = _open_current_token(TOKEN_QUERY)
        try:
            restricted = bool(_query_dword(token, TokenHasRestrictions))
            elevation = _query_dword(token, TokenElevationType)
            integrity = _integrity_rid(token)
            # Low integrity is a useful independent boundary check. Restricted
            # is mandatory; medium/high integrity is rejected.
            if not restricted or integrity >= 0x3000:
                raise WorkerSecurityError(
                    f"worker token is not sufficiently restricted: "
                    f"restricted={restricted}, integrity_rid={integrity}"
                )
            return WorkerTokenReport(restricted, integrity, elevation)
        finally:
            kernel32.CloseHandle(token)

    def create_restricted_worker(command_line: str, stdin_handle: int):
        token = _open_current_token(
            TOKEN_QUERY | TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY
            | TOKEN_ADJUST_DEFAULT | TOKEN_ADJUST_SESSIONID
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
            si.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
            si.hStdInput = wintypes.HANDLE(stdin_handle)
            pi = PROCESS_INFORMATION()
            if not advapi32.CreateProcessAsUserW(
                restricted, None, ctypes.create_unicode_buffer(command_line),
                None, None, True, 0, None, None, ctypes.byref(si), ctypes.byref(pi)
            ):
                _raise_last_error("CreateProcessAsUserW failed for restricted worker")
            return pi
        finally:
            kernel32.CloseHandle(restricted)
            kernel32.CloseHandle(token)
