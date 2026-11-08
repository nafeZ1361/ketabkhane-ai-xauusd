"""Signal contracts (Phase 3, S1). Pure data; no MT5, no orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class SignalError(ValueError):
    """Raised when a signal would be ambiguous or unsafe."""


@dataclass(frozen=True, slots=True)
class Signal:
    symbol: str
    timeframe: str
    bar_time_utc: datetime
    direction: Direction
    strength: Decimal
    strategy_id: str
    reason_code: str

    def __post_init__(self) -> None:
        if self.bar_time_utc.tzinfo is None or self.bar_time_utc.tzinfo.utcoffset(self.bar_time_utc) is None:
            raise SignalError("bar_time_utc must be timezone-aware")
        names = ("symbol", "timeframe", "strategy_id", "reason_code")
        for name in names:
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise SignalError(f"{name} is required")
        if not isinstance(self.direction, Direction):
            raise SignalError(f"unknown direction: {self.direction!r}")
        if not isinstance(self.strength, Decimal) or not self.strength.is_finite():
            raise SignalError("strength must be a finite Decimal")
        if not Decimal(0) <= self.strength <= Decimal(1):
            raise SignalError(f"strength out of range: {self.strength}")


KNOWN_PARAMS = frozenset({"fast", "slow"})


@dataclass(frozen=True, slots=True)
class StrategySpec:
    id: str
    version: str
    params: Mapping[str, Decimal]
    warmup_bars: int

    def __post_init__(self) -> None:
        if self.warmup_bars < 0:
            raise SignalError("warmup_bars must be non-negative")
        for name in ("id", "version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise SignalError(f"{name} is required")
        if not isinstance(self.params, Mapping):
            raise SignalError("params must be a mapping")
        unknown = set(self.params) - KNOWN_PARAMS
        if unknown:
            raise SignalError(f"unknown params: {sorted(unknown)}")
        for key, value in self.params.items():
            if not isinstance(value, Decimal):
                raise SignalError(f"param {key!r} must be Decimal")
            if not value.is_finite():
                raise SignalError(f"param {key!r} must be finite")


@dataclass(frozen=True, slots=True)
class SignalRun:
    run_id: str
    strategy_id: str
    timeframe: str
    from_utc: datetime
    to_utc: datetime
    bars_seen: int
    signals: int
    status: str = "OK"

    def __post_init__(self) -> None:
        for name in ("run_id", "strategy_id", "timeframe"):
            if not getattr(self, name).strip():
                raise SignalError(f"{name} is required")
        for name in ("from_utc", "to_utc"):
            moment = getattr(self, name)
            if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
                raise SignalError("run window must be timezone-aware")
        if self.from_utc >= self.to_utc:
            raise SignalError("empty run window")
