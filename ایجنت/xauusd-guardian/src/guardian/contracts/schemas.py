"""Versioned data contracts shared across every layer.

Rules for this module:
- no I/O, no MT5 import, no logging side effects;
- every contract carries a ``schema_version`` where it crosses a process or
  storage boundary;
- validation happens in ``__post_init__`` and fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

SCHEMA_VERSION = 2

#: Broker stop distance is expressed in points; one point is ``tick_size``.
POINT_FACTOR = 1.0


class ExecutionMode(str, Enum):
    """Execution modes. There is deliberately no live mode."""

    DRY_RUN = "DRY_RUN"
    SIMULATED = "SIMULATED"
    DEMO = "DEMO"  # requires a separate approval (A-05); rejected by the loader


class TradeMode(str, Enum):
    DEMO = "DEMO"
    CONTEST = "CONTEST"
    REAL = "REAL"

    @classmethod
    def from_mt5(cls, value: Any) -> "TradeMode":
        mapping = {0: cls.DEMO, 1: cls.CONTEST, 2: cls.REAL}
        try:
            return mapping[int(value)]
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"unknown MT5 trade_mode: {value!r}") from None


class ResolutionStatus(str, Enum):
    """Outcome of gold-symbol resolution. Only ``VERIFIED`` is permissive.

    ``RESOLVED`` is retired and deliberately **not** an alias of ``VERIFIED``:
    it is the pre-D-003 success value returned by the legacy scoring policies,
    which perform no metadata corroboration. Keeping it distinct guarantees
    that no scoring policy can ever open the gate (audit finding F1).
    """

    VERIFIED = "VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    METADATA_MISMATCH = "METADATA_MISMATCH"
    AMBIGUOUS = "AMBIGUOUS"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    RESOLVED = "RESOLVED"


class RiskStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    REJECTED_LOW_EFFECTIVE_RISK = "REJECTED_LOW_EFFECTIVE_RISK"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    """Validated snapshot of one broker symbol. Never cached across sessions."""

    name: str
    path: str = ""
    description: str = ""
    trade_mode: int = 0
    digits: int = 0
    point: float = 0.0
    tick_size: float = 0.0
    tick_value: float = 0.0
    contract_size: float = 0.0
    volume_min: float = 0.0
    volume_max: float = 0.0
    volume_step: float = 0.0
    stops_level: int = 0
    freeze_level: int = 0
    filling_mode: int = 0
    currency_base: str = ""
    currency_profit: str = ""
    visible: bool = False
    trade_allowed_by_broker: bool = True

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("SymbolSpec.name is required")
        if self.digits < 0:
            raise ValueError(f"{self.name}: digits must be >= 0")
        for attr in ("point", "tick_size", "tick_value", "contract_size"):
            if getattr(self, attr) < 0:
                raise ValueError(f"{self.name}: {attr} must be >= 0")
        if self.volume_step < 0:
            raise ValueError(f"{self.name}: volume_step must be >= 0")

    @property
    def is_tradable(self) -> bool:
        return self.trade_mode == 4 and self.visible


#: ``ranked`` entries are ordered ``(score, name)`` — see ``reporting.ranking``.
RankedSymbol = tuple[int, str]

#: Symbol fields that establish *which instrument* this is.
IDENTITY_FIELDS = ("name", "path", "currency_profit")
#: Fields describing price formatting, not identity.
FORMATTING_FIELDS = ("contract_size", "tick_size", "digits")
#: Fields describing broker authorization to trade, not identity.
AUTHORIZATION_FIELDS = ("trade_mode",)


@dataclass(frozen=True, slots=True)
class SymbolResolution:
    """Result of gold-symbol identification.

    ``ranked`` holds ``(score, name)`` pairs, highest score first. ``mismatches``
    holds ``(field, expected, actual)`` triples for ``METADATA_MISMATCH``.
    """

    status: ResolutionStatus
    policy: str
    symbol_name: str | None = None
    ranked: tuple[RankedSymbol, ...] = ()
    margin: int | None = None
    reason: str = ""
    mismatches: tuple[tuple[str, str, str], ...] = ()
    observed: tuple[tuple[str, str], ...] = ()
    schema_version: int = SCHEMA_VERSION

    @property
    def ok(self) -> bool:
        return self.status is ResolutionStatus.VERIFIED

    @property
    def primary_mismatch(self) -> tuple[str, str, str] | None:
        return self.mismatches[0] if self.mismatches else None


@dataclass(frozen=True, slots=True)
class SignalCandidate:
    """Strategy output. Never an execution authorization."""

    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float | None
    reason: str
    strategy_version: str
    timestamp_utc: datetime = field(default_factory=utc_now)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.direction not in ("BUY", "SELL"):
            raise ValueError(f"invalid direction: {self.direction!r}")
        if not self.strategy_version:
            raise ValueError("strategy_version is required")
        if self.stop_loss is None:
            raise ValueError("stop_loss is mandatory")
        if self.direction == "BUY" and not self.stop_loss < self.entry_price:
            raise ValueError("BUY requires stop_loss < entry_price")
        if self.direction == "SELL" and not self.stop_loss > self.entry_price:
            raise ValueError("SELL requires stop_loss > entry_price")


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Risk manager verdict, independently revalidated by the firewall."""

    decision_id: str
    status: RiskStatus
    symbol: str
    volume: float = 0.0
    target_risk_percent: float = 0.0
    effective_risk_percent: float = 0.0
    reason: str = ""
    symbol_spec: Mapping[str, Any] | None = None
    timestamp_utc: datetime = field(default_factory=utc_now)
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.decision_id:
            raise ValueError("decision_id is required")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")

    @property
    def authorizes_execution(self) -> bool:
        return self.status is RiskStatus.ACCEPTED and self.volume > 0
