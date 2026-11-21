"""Position sizing — Phase 4.

One pure function answers one question: for a given equity, risk fraction and stop
distance, how many lots may be opened *without exceeding that risk*?

Design rules (pre-registered in ``DECISIONS_LOG.md`` D-023):

* ``Decimal`` only. ``float`` and ``int`` are refused so no binary rounding can creep in.
* Fail closed. Every inconsistent or non-finite input raises :class:`RiskError`; the
  function never returns a best-effort number, never returns a negative size and never
  silently rounds up.
* Round **down** to ``lot_step`` so the realised risk is at or below the requested risk.
* Clamp to ``max_lot`` (a broker/owner cap), never above it.
* No account access, no ``MetaTrader5``, no order construction. The caller supplies the
  equity number; this module does not know what a terminal is.

The contract is deliberately narrow: sizing is arithmetic, not advice.
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
    """Instrument economics and the owner's risk limits for one symbol.

    ``value_per_point_lot`` is the account-currency value of one point for one lot;
    ``lot_step`` is the broker's volume increment. All fields are ``Decimal`` because the
    result feeds a numeric decision that must be reproducible.
    """

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
    """Lots to trade, or :class:`RiskError` — never a guess.

    ``equity`` is a number the caller obtained elsewhere (this module never reads an
    account). ``stop_points`` is the distance from entry to stop in points, strictly
    positive. The result is a multiple of ``spec.lot_step``, at least ``spec.min_lot``,
    at most ``spec.max_lot``, and its risk never exceeds ``equity * risk_fraction``.
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
    if risk_per_lot <= 0:  # defensive: both factors are already validated positive
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
    if lots > spec.max_lot:
        return spec.max_lot
    return lots
