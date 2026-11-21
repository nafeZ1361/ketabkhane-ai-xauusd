"""Pure portfolio-level risk gates over caller-supplied values.

No account, broker, MT5 or order access. Callers must supply verified snapshots.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from .sizing import RiskError, _require_decimal


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_daily_loss_fraction: Decimal
    max_weekly_loss_fraction: Decimal
    max_drawdown_fraction: Decimal
    max_open_risk_fraction: Decimal
    max_consecutive_losses: int

    def __post_init__(self) -> None:
        for name in (
            "max_daily_loss_fraction", "max_weekly_loss_fraction",
            "max_drawdown_fraction", "max_open_risk_fraction",
        ):
            value = _require_decimal(name, getattr(self, name))
            if not Decimal(0) < value < Decimal(1):
                raise RiskError(f"{name} must be strictly between 0 and 1")
        if isinstance(self.max_consecutive_losses, bool) or not isinstance(self.max_consecutive_losses, int):
            raise RiskError("max_consecutive_losses must be an integer")
        if self.max_consecutive_losses < 1:
            raise RiskError("max_consecutive_losses must be positive")


@dataclass(frozen=True, slots=True)
class RiskSnapshot:
    current_equity: Decimal
    day_start_equity: Decimal
    week_start_equity: Decimal
    peak_equity: Decimal
    open_risk_amount: Decimal
    consecutive_losses: int


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate_risk(snapshot: RiskSnapshot, limits: RiskLimits) -> RiskDecision:
    """Fail-closed gate; values are synthetic/caller-supplied until A-04 exists."""
    if not isinstance(snapshot, RiskSnapshot) or not isinstance(limits, RiskLimits):
        raise RiskError("snapshot and limits must use their declared contracts")
    names = ("current_equity", "day_start_equity", "week_start_equity", "peak_equity", "open_risk_amount")
    values = {name: _require_decimal(name, getattr(snapshot, name)) for name in names}
    for name in ("current_equity", "day_start_equity", "week_start_equity", "peak_equity"):
        if values[name] <= 0:
            raise RiskError(f"{name} must be positive")
    if values["open_risk_amount"] < 0:
        raise RiskError("open_risk_amount cannot be negative")
    if isinstance(snapshot.consecutive_losses, bool) or not isinstance(snapshot.consecutive_losses, int):
        raise RiskError("consecutive_losses must be an integer")
    if snapshot.consecutive_losses < 0:
        raise RiskError("consecutive_losses cannot be negative")

    current = values["current_equity"]
    daily_loss = max(Decimal(0), (values["day_start_equity"] - current) / values["day_start_equity"])
    weekly_loss = max(Decimal(0), (values["week_start_equity"] - current) / values["week_start_equity"])
    drawdown = max(Decimal(0), (values["peak_equity"] - current) / values["peak_equity"])
    open_risk = values["open_risk_amount"] / current

    reasons: list[str] = []
    if daily_loss >= limits.max_daily_loss_fraction:
        reasons.append("DAILY_LOSS_LIMIT")
    if weekly_loss >= limits.max_weekly_loss_fraction:
        reasons.append("WEEKLY_LOSS_LIMIT")
    if drawdown >= limits.max_drawdown_fraction:
        reasons.append("MAX_DRAWDOWN")
    if open_risk >= limits.max_open_risk_fraction:
        reasons.append("AGGREGATE_OPEN_RISK_LIMIT")
    if snapshot.consecutive_losses >= limits.max_consecutive_losses:
        reasons.append("CONSECUTIVE_LOSS_LIMIT")
    return RiskDecision(allowed=not reasons, reasons=tuple(reasons))
