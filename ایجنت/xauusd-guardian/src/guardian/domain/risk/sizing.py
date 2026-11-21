"""Position sizing — Phase 4.

Pure Decimal arithmetic. No account access, MT5 import, or order construction.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR

class RiskError(ValueError):
    """Raised when a sizing request cannot be honoured safely."""

def _require_decimal(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise RiskError(f"{name} must be Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise RiskError(f"{name} must be finite")
    return value

@dataclass(frozen=True, slots=True)
class RiskSpec:
    """Instrument economics and per-trade risk limits."""
    risk_fraction: Decimal
    value_per_point_lot: Decimal
    lot_step: Decimal
    min_lot: Decimal
    max_lot: Decimal

    def __post_init__(self) -> None:
        for name in ("risk_fraction", "value_per_point_lot", "lot_step", "min_lot", "max_lot"):
            _require_decimal(name, getattr(self, name))
        if not (Decimal(0) < self.risk_fraction < Decimal(1)):
            raise RiskError("risk_fraction must be strictly between 0 and 1")
        if self.value_per_point_lot <= 0:
            raise RiskError("value_per_point_lot must be positive")
        if self.lot_step <= 0:
            raise RiskError("lot_step must be positive")
        if self.min_lot <= 0:
            raise RiskError("min_lot must be positive")
        if self.max_lot < self.min_lot:
            raise RiskError("max_lot must be greater than or equal to min_lot")
        if self.min_lot % self.lot_step != 0:
            raise RiskError("min_lot must be a multiple of lot_step")

def position_size(equity: Decimal, stop_points: Decimal, spec: RiskSpec) -> Decimal:
    """Return a valid lot-step multiple within the risk budget and broker cap.

    max_lot is a ceiling, not necessarily a valid volume increment. Floor the
    effective cap to lot_step rather than returning an invalid raw cap.
    """
    if not isinstance(spec, RiskSpec):
        raise RiskError("spec must be a RiskSpec")
    _require_decimal("equity", equity)
    _require_decimal("stop_points", stop_points)
    if equity <= 0:
        raise RiskError("equity must be positive")
    if stop_points <= 0:
        raise RiskError("stop_points must be positive")
    risk_amount = equity * spec.risk_fraction
    risk_per_lot = stop_points * spec.value_per_point_lot
    if risk_per_lot <= 0:
        raise RiskError("risk per lot must be positive")
    raw_lots = risk_amount / risk_per_lot
    steps = (raw_lots / spec.lot_step).to_integral_value(rounding=ROUND_FLOOR)
    lots = steps * spec.lot_step
    if lots <= 0:
        raise RiskError(
            f"computed size is below one lot step ({spec.lot_step}); "
            f"raw={raw_lots}, risk_amount={risk_amount}, risk_per_lot={risk_per_lot}"
        )
    if lots < spec.min_lot:
        raise RiskError(f"computed size {lots} is below min_lot {spec.min_lot}")
    cap_steps = (spec.max_lot / spec.lot_step).to_integral_value(rounding=ROUND_FLOOR)
    effective_cap = cap_steps * spec.lot_step
    if effective_cap < spec.min_lot:
        raise RiskError("max_lot does not permit one valid lot-step at or above min_lot")
    return min(lots, effective_cap)
