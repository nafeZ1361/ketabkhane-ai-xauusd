"""Persistent fail-safe kill-switch state for the Phase 5 firewall.

The kill switch is a safety state boundary, not an execution authorization API.
Any state ambiguity is interpreted as ACTIVE.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


_VERSION = 1
_ACTIVE = "ACTIVE"
_CLEAR = "CLEAR"
_STATES = frozenset({_ACTIVE, _CLEAR})
_FIELDS = ("version", "state", "generation", "updated_at_utc")


class KillSwitchError(RuntimeError):
    """Raised when a requested state transition cannot be persisted safely."""


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    version: int
    state: str
    generation: int
    updated_at_utc: str

    @property
    def active(self) -> bool:
        return self.state == _ACTIVE


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(state: KillSwitchState) -> bytes:
    value = {
        "version": state.version,
        "state": state.state,
        "generation": state.generation,
        "updated_at_utc": state.updated_at_utc,
    }
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _invalid() -> KillSwitchState:
    return KillSwitchState(_VERSION, _ACTIVE, 0, "INVALID")


def _parse(raw: bytes) -> KillSwitchState:
    try:
        value = json.loads(raw.decode("utf-8"))
        if type(value) is not dict or set(value) != set(_FIELDS):
            return _invalid()
        version = value["version"]
        state = value["state"]
        generation = value["generation"]
        updated = value["updated_at_utc"]
        if type(version) is not int or version != _VERSION:
            return _invalid()
        if type(state) is not str or state not in _STATES:
            return _invalid()
        if type(generation) is not int or generation < 1:
            return _invalid()
        if type(updated) is not str or not updated.endswith("Z"):
            return _invalid()
        # Canonical encoding is part of the integrity contract. Non-canonical
        # records are ambiguous and therefore fail closed.
        candidate = KillSwitchState(version, state, generation, updated)
        if _canonical_bytes(candidate) != raw:
            return _invalid()
        return candidate
    except Exception:
        return _invalid()


def _safe_read(path: Path) -> KillSwitchState:
    try:
        return _parse(path.read_bytes())
    except Exception:
        return _invalid()


class KillSwitchStore:
    """Persistent kill switch with fail-safe reads and compare-and-swap recovery."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        if not self.path.name or self.path.name in {".", ".."}:
            raise ValueError("invalid kill-switch path")

    def read(self) -> KillSwitchState:
        return _safe_read(self.path)

    def is_active(self) -> bool:
        return self.read().active

    def _persist(self, state: KillSwitchState) -> None:
        parent = self.path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", suffix=".tmp", dir=str(parent)
            )
            try:
                data = _canonical_bytes(state)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, self.path)
                # Verify the committed bytes before reporting success.
                if _safe_read(self.path) != state:
                    raise KillSwitchError("kill-switch persistence verification failed")
            finally:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
        except KillSwitchError:
            raise
        except Exception as exc:
            raise KillSwitchError("kill-switch persistence failed") from exc

    def activate(self) -> KillSwitchState:
        current = self.read()
        generation = max(0, current.generation) + 1
        candidate = KillSwitchState(_VERSION, _ACTIVE, generation, _now_utc())
        # If persistence fails, the effective state remains ACTIVE because reads
        # fail closed regardless of the caller's in-memory state.
        self._persist(candidate)
        return candidate

    def recover(self, *, expected_generation: int) -> KillSwitchState:
        current = self.read()
        if current.active is False:
            return current
        if type(expected_generation) is not int:
            raise KillSwitchError("invalid recovery generation")
        if current.generation != expected_generation:
            raise KillSwitchError("stale recovery generation")
        candidate = KillSwitchState(_VERSION, _CLEAR, current.generation + 1, _now_utc())
        self._persist(candidate)
        return candidate
