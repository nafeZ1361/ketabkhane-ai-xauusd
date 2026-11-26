"""Independent, pure risk revalidation at the Phase 5 firewall boundary.

This module validates a proposed size against a fresh Phase 4 recomputation.
A successful result is NOT an execution authorization. F2 remains authoritative
and continues to deny every order/execution operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from guardian.domain.risk import RiskSpec, position_size


@dataclass(frozen=True, slots=True)
class RiskBoundaryDecision:
    """Immutable result of arithmetic validation; never an execution capability."""

    within_risk_limit: bool
    reason_code: str
    recomputed_max_lots: Decimal | None


def _exact_decimal(value: object) -> bool:
    return type(value) is Decimal and value.is_finite()


def _deny(reason: str, maximum: Decimal | None = None) -> RiskBoundaryDecision:
    return RiskBoundaryDecision(False, reason, maximum)


def revalidate_proposed_size(
    equity: Decimal,
    stop_points: Decimal,
    proposed_lots: Decimal,
    *,
    spec: RiskSpec,
) -> RiskBoundaryDecision:
    """Recompute and validate a proposed lot size using a separately supplied spec.

    The spec is a trusted-caller input, not read from the untrusted firewall payload.
    Equity and stop_points are explicit inputs; this function performs no account,
    broker, filesystem, network, or environment access. Their provenance is not
    established here and must be authenticated by a separately authorized integration.
    A PASS means only that the arithmetic is within this supplied spec.
    """
    if type(spec) is not RiskSpec:
        return _deny("INVALID_RISK_SPEC")
    if not all(_exact_decimal(value) for value in (equity, stop_points, proposed_lots)):
        return _deny("INVALID_DECIMAL_INPUT")

    try:
        # Reconstruct to detect low-level mutation of the frozen Phase 4 dataclass.
        fields = (
            spec.risk_fraction,
            spec.value_per_point_lot,
            spec.lot_step,
            spec.min_lot,
            spec.max_lot,
        )
        if not all(_exact_decimal(value) for value in fields):
            return _deny("INVALID_RISK_SPEC")
        safe_spec = RiskSpec(
            risk_fraction=fields[0],
            value_per_point_lot=fields[1],
            lot_step=fields[2],
            min_lot=fields[3],
            max_lot=fields[4],
        )
        # Require the broker cap itself to be step-aligned. Phase 4 permits a
        # non-aligned max_lot; accepting that here could yield an off-step cap.
        if safe_spec.max_lot % safe_spec.lot_step != 0:
            return _deny("INVALID_RISK_SPEC")

        maximum = position_size(equity, stop_points, safe_spec)
        if not _exact_decimal(maximum):
            return _deny("RISK_RECOMPUTATION_INVALID", maximum)

        if proposed_lots <= 0:
            return _deny("PROPOSED_SIZE_NOT_POSITIVE", maximum)
        if proposed_lots < safe_spec.min_lot:
            return _deny("PROPOSED_SIZE_BELOW_MINIMUM", maximum)
        if proposed_lots > safe_spec.max_lot or proposed_lots > maximum:
            return _deny("PROPOSED_SIZE_EXCEEDS_RECOMPUTED_MAXIMUM", maximum)
        if proposed_lots % safe_spec.lot_step != 0:
            return _deny("PROPOSED_SIZE_OFF_STEP", maximum)

        proposed_risk = proposed_lots * stop_points * safe_spec.value_per_point_lot
        risk_budget = equity * safe_spec.risk_fraction
        if proposed_risk > risk_budget:
            return _deny("PROPOSED_RISK_EXCEEDS_BUDGET", maximum)

        return RiskBoundaryDecision(True, "RISK_WITHIN_LIMIT", maximum)
    except Exception:
        # Decimal context errors, hostile mutated fields and unexpected arithmetic
        # failures must never escape as a permissive result.
        return _deny("RISK_REVALIDATION_FAILED")
