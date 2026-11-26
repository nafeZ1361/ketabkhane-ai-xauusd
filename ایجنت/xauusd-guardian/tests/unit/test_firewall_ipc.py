"""F4 authenticated IPC framing, authentication, ordering and replay tests."""

from io import BytesIO
import json

import pytest

from guardian.firewall.ipc import (
    AuthenticatedCodec,
    IPCProtocolError,
    MAX_FRAME_BYTES,
    canonical_json,
    read_frame,
    write_frame,
)


KEY = b"k" * 32
SESSION = "ab" * 32


def endpoints(session=SESSION, key=KEY):
    parent = AuthenticatedCodec(
        key=key, session_id=session,
        send_direction="parent_to_worker",
        receive_direction="worker_to_parent",
    )
    worker = AuthenticatedCodec(
        key=key, session_id=session,
        send_direction="worker_to_parent",
        receive_direction="parent_to_worker",
    )
    return parent, worker


def test_authenticated_request_response_round_trip():
    parent, worker = endpoints()
    request_body = parent.encode("HEALTH_CHECK", "corr-1", {})
    request = worker.decode(request_body)
    assert request.message_type == "HEALTH_CHECK"
    assert request.sequence == 1
    assert request.correlation_id == "corr-1"
    response_body = worker.encode("RESULT", "corr-1", {"status": "OK"})
    response = parent.decode(response_body)
    assert response.message_type == "RESULT"
    assert response.payload == {"status": "OK"}
    assert parent.send_sequence == worker.receive_sequence == 1


def test_frame_length_prefix_round_trip():
    body = b'{"safe":true}'
    stream = BytesIO()
    write_frame(stream, body)
    stream.seek(0)
    assert read_frame(stream) == body


@pytest.mark.parametrize("prefix", [b"\x00\x00\x00\x00", (MAX_FRAME_BYTES + 1).to_bytes(4, "big")])
def test_zero_and_oversized_frames_are_rejected(prefix):
    with pytest.raises(IPCProtocolError):
        read_frame(BytesIO(prefix))


def test_truncated_header_and_body_are_rejected():
    with pytest.raises(IPCProtocolError, match="TRUNCATED_FRAME"):
        read_frame(BytesIO(b"\x00\x00"))
    with pytest.raises(IPCProtocolError, match="TRUNCATED_FRAME"):
        read_frame(BytesIO(b"\x00\x00\x00\x04ab"))


def test_oversized_write_is_rejected():
    with pytest.raises(IPCProtocolError, match="FRAME_SIZE_LIMIT"):
        write_frame(BytesIO(), b"x" * (MAX_FRAME_BYTES + 1))


def test_payload_tampering_fails_authentication():
    parent, worker = endpoints()
    body = parent.encode("HEALTH_CHECK", "corr", {})
    envelope = json.loads(body)
    envelope["payload"] = {"admin": True}
    tampered = canonical_json(envelope)
    with pytest.raises(IPCProtocolError, match="AUTHENTICATION_FAILED"):
        worker.decode(tampered)


def test_wrong_key_fails_authentication():
    parent, _ = endpoints()
    _, wrong_worker = endpoints(key=b"z" * 32)
    body = parent.encode("HEALTH_CHECK", "corr", {})
    with pytest.raises(IPCProtocolError, match="AUTHENTICATION_FAILED"):
        wrong_worker.decode(body)


def test_duplicate_frame_is_replay_and_rejected():
    parent, worker = endpoints()
    body = parent.encode("HEALTH_CHECK", "corr", {})
    worker.decode(body)
    with pytest.raises(IPCProtocolError, match="SEQUENCE_REPLAY_OR_GAP"):
        worker.decode(body)


def test_sequence_gap_and_out_of_order_frames_are_rejected():
    parent, worker = endpoints()
    first = parent.encode("HEALTH_CHECK", "first", {})
    second = parent.encode("HEALTH_CHECK", "second", {})
    with pytest.raises(IPCProtocolError, match="SEQUENCE_REPLAY_OR_GAP"):
        worker.decode(second)
    assert worker.receive_sequence == 0
    assert worker.decode(first).sequence == 1
    assert worker.decode(second).sequence == 2


def test_cross_session_frame_is_rejected():
    parent, _ = endpoints()
    _, other_worker = endpoints(session="cd" * 32)
    body = parent.encode("HEALTH_CHECK", "corr", {})
    with pytest.raises(IPCProtocolError, match="SESSION_MISMATCH"):
        other_worker.decode(body)


def test_wrong_direction_frame_is_rejected():
    sender, _ = endpoints()
    _, receiver = endpoints()
    body = sender.encode("HEALTH_CHECK", "corr", {})
    with pytest.raises(IPCProtocolError, match="DIRECTION_MISMATCH"):
        sender.decode(body)


def test_unknown_message_type_and_non_object_payload_are_rejected():
    parent, _ = endpoints()
    with pytest.raises(IPCProtocolError, match="MESSAGE_TYPE_NOT_ALLOWED"):
        parent.encode("ORDER_SEND", "corr", {})
    with pytest.raises(IPCProtocolError, match="PAYLOAD_NOT_OBJECT"):
        parent.encode("HEALTH_CHECK", "corr", [])


@pytest.mark.parametrize("session", ["", "g" * 64, "a" * 63 + " "])
def test_malformed_session_ids_are_rejected(session):
    with pytest.raises(IPCProtocolError, match="INVALID_SESSION_ID"):
        AuthenticatedCodec(
            key=KEY, session_id=session,
            send_direction="parent_to_worker",
            receive_direction="worker_to_parent",
        )


def test_noncanonical_json_is_rejected():
    parent, worker = endpoints()
    body = parent.encode("HEALTH_CHECK", "corr", {})
    envelope = json.loads(body)
    pretty = json.dumps(envelope, indent=2).encode("utf-8")
    with pytest.raises(IPCProtocolError, match="NON_CANONICAL_JSON"):
        worker.decode(pretty)


def test_duplicate_json_keys_are_rejected():
    body = b'{"a":1,"a":2}'
    from guardian.firewall.ipc import _parse_canonical
    with pytest.raises(IPCProtocolError, match="DUPLICATE_JSON_KEY"):
        _parse_canonical(body)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_json_numbers_are_rejected(value):
    with pytest.raises(IPCProtocolError):
        canonical_json({"value": value})


def test_excessive_nesting_is_rejected():
    nested = {}
    cursor = nested
    for _ in range(40):
        cursor["x"] = {}
        cursor = cursor["x"]
    with pytest.raises(IPCProtocolError, match="JSON_NESTING_LIMIT"):
        canonical_json(nested)


def test_sequence_only_advances_after_successful_verification():
    parent, worker = endpoints()
    body = parent.encode("HEALTH_CHECK", "corr", {})
    envelope = json.loads(body)
    envelope["tag"] = "0" * 64
    with pytest.raises(IPCProtocolError, match="AUTHENTICATION_FAILED"):
        worker.decode(canonical_json(envelope))
    assert worker.receive_sequence == 0
    assert worker.decode(body).sequence == 1


def test_tag_is_direction_domain_separated():
    parent, worker = endpoints()
    body = parent.encode("HEALTH_CHECK", "corr", {})
    envelope = json.loads(body)
    unsigned = {key: value for key, value in envelope.items() if key != "tag"}
    envelope["direction"] = "worker_to_parent"
    with pytest.raises(IPCProtocolError):
        worker.decode(canonical_json({**unsigned, "direction": "worker_to_parent"}))


def test_destroy_zeroizes_ephemeral_session_key():
    codec = AuthenticatedCodec(
        key=bytearray(b"z" * 32),
        session_id="ef" * 32,
        send_direction="parent_to_worker",
        receive_direction="worker_to_parent",
    )
    key_reference = codec._key
    codec.destroy()
    assert key_reference == bytearray()
    assert codec._session_id == ""
    with pytest.raises(IPCProtocolError, match="INVALID_SESSION_KEY"):
        AuthenticatedCodec(
            key=codec._key,
            session_id="ef" * 32,
            send_direction="parent_to_worker",
            receive_direction="worker_to_parent",
        )
