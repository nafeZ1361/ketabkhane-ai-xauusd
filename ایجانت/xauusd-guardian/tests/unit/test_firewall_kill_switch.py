"""F5 persistent fail-safe kill-switch tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from guardian.firewall.kill_switch import KillSwitchError, KillSwitchStore


def test_missing_state_fails_closed(tmp_path: Path):
    store = KillSwitchStore(tmp_path / "kill-switch.json")
    assert store.is_active() is True
    assert store.read().state == "ACTIVE"


def test_activation_persists_across_new_store(tmp_path: Path):
    path = tmp_path / "kill-switch.json"
    first = KillSwitchStore(path)
    state = first.activate()
    second = KillSwitchStore(path)
    assert state.active is True
    assert second.read() == state
    assert second.is_active() is True


def test_recovery_is_explicit_and_survives_restart(tmp_path: Path):
    path = tmp_path / "kill-switch.json"
    store = KillSwitchStore(path)
    active = store.activate()
    cleared = store.recover(expected_generation=active.generation)
    assert cleared.active is False
    assert KillSwitchStore(path).is_active() is False


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{}\n",
        b'{"version":2,"state":"CLEAR","generation":1,"updated_at_utc":"2026-01-01T00:00:00Z"}\n',
        b'{"version":1,"state":"BOGUS","generation":1,"updated_at_utc":"2026-01-01T00:00:00Z"}\n',
        b'{"version":1,"state":"CLEAR","generation":0,"updated_at_utc":"2026-01-01T00:00:00Z"}\n',
        b'{"version":1,"state":"CLEAR","generation":1,"updated_at_utc":"2026-01-01T00:00:00Z","extra":1}\n',
    ],
)
def test_corrupt_or_ambiguous_state_fails_closed(tmp_path: Path, raw: bytes):
    path = tmp_path / "kill-switch.json"
    path.write_bytes(raw)
    assert KillSwitchStore(path).is_active() is True


def test_recovery_requires_current_generation(tmp_path: Path):
    store = KillSwitchStore(tmp_path / "kill-switch.json")
    active = store.activate()
    with pytest.raises(KillSwitchError, match="stale recovery generation"):
        store.recover(expected_generation=active.generation + 1)
    assert store.is_active() is True


def test_recovery_never_auto_clears(tmp_path: Path):
    path = tmp_path / "kill-switch.json"
    store = KillSwitchStore(path)
    active = store.activate()
    assert KillSwitchStore(path).read().generation == active.generation
    assert KillSwitchStore(path).is_active() is True


def test_persistence_failure_fails_safe(tmp_path: Path, monkeypatch):
    store = KillSwitchStore(tmp_path / "kill-switch.json")
    def fail_replace(*args, **kwargs):
        raise OSError("simulated replace failure")
    monkeypatch.setattr("guardian.firewall.kill_switch.os.replace", fail_replace)
    with pytest.raises(KillSwitchError):
        store.activate()
    assert store.is_active() is True


def test_canonical_record_is_rejected_if_rewritten_noncanonically(tmp_path: Path):
    path = tmp_path / "kill-switch.json"
    store = KillSwitchStore(path)
    store.activate()
    value = json.loads(path.read_text())
    path.write_text(json.dumps(value, indent=2) + "\n")
    assert store.is_active() is True
