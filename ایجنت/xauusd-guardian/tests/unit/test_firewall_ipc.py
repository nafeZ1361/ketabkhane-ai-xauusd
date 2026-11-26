import json
import socket
import time

import pytest

from guardian.firewall.ipc import AuthenticatedSession, IPCError, recv_frame, send_frame


def test_authenticated_round_trip_and_monotonic_sequence():
    a = AuthenticatedSession(b"k" * 32, b"n" * 16)
    b = AuthenticatedSession(b"k" * 32, b"n" * 16)
    frame = a.encode({"type": "hello"})
    assert b.decode(frame[4:]) == {"type": "hello"}
    with pytest.raises(IPCError, match="replayed"):
        b.decode(frame[4:])


def test_forged_mac_denied():
    a = AuthenticatedSession(b"k" * 32, b"n" * 16)
    b = AuthenticatedSession(b"x" * 32, b"n" * 16)
    frame = a.encode({"type": "hello"})
    with pytest.raises(IPCError, match="authentication"):
        b.decode(frame[4:])


def test_wrong_session_nonce_denied():
    a = AuthenticatedSession(b"k" * 32, b"n" * 16)
    b = AuthenticatedSession(b"k" * 32, b"m" * 16)
    frame = a.encode({"type": "hello"})
    with pytest.raises(IPCError, match="nonce"):
        b.decode(frame[4:])


def test_stale_frame_denied(monkeypatch):
    a = AuthenticatedSession(b"k" * 32, b"n" * 16)
    b = AuthenticatedSession(b"k" * 32, b"n" * 16)
    frame = a.encode({"type": "hello"})
    envelope = json.loads(frame[4:].decode())
    envelope["ts"] = time.time() - 60
    forged = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()
    with pytest.raises(IPCError, match="stale"):
        b.decode(forged)


def test_frame_size_is_bounded():
    a = AuthenticatedSession(b"k" * 32, b"n" * 16)
    with pytest.raises(IPCError, match="too large"):
        a.encode({"data": "x" * 70000})


def test_socket_frame_helpers():
    left, right = socket.socketpair()
    try:
        send_frame(left, b"abc")
        assert recv_frame(right) == b"abc"
    finally:
        left.close()
        right.close()


def test_worker_security_is_fail_closed_off_windows():
    from guardian.firewall import worker_security

    if worker_security.os.name != "nt":
        with pytest.raises(worker_security.WorkerSecurityError):
            worker_security.verify_current_worker_token()
