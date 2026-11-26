"""F3 independent risk revalidation at the firewall boundary."""

from decimal import Decimal, Inexact, localcontext

import pytest

from guardian.domain.risk import RiskSpec
from guardian.firewall.risk import RiskBoundaryDecision, revalidate_proposed_size


def spec(**overrides):
    values = {
        "risk_fraction": Decimal("0.01"),
        "value_per_point_lot": Decimal("1"),
        "lot_step": Decimal("0.01"),
        "min_lot": Decimal("0.01"),
        "max_lot": Decimal("100"),
    }
    values.update(overrides)
    return RiskSpec(**values)


def validate(lots, *, equity=Decimal("10000"), stop=Decimal("100"), risk_spec=None):
    return revalidate_proposed_size(
        equity, stop, lots, spec=spec() if risk_spec is None else risk_spec
    )


def test_exact_recomputed_maximum_is_accepted():
    result = validate(Decimal("1.00"))
    assert result == RiskBoundaryDecision(True, "RISK_WITHIN_LIMIT", Decimal("1.00"))


def test_smaller_step_aligned_size_is_accepted():
    result = validate(Decimal("0.50"))
    assert result.within_risk_limit is True
    assert result.reason_code == "RISK_WITHIN_LIMIT"
    assert result.recomputed_max_lots == Decimal("1.00")


@pytest.mark.parametrize(
    ("lots", "reason"),
    [
        (Decimal("1.01"), "PROPOSED_SIZE_EXCEEDS_RECOMPUTED_MAXIMUM"),
        (Decimal("0.005"), "PROPOSED_SIZE_BELOW_MINIMUM"),
        (Decimal("0"), "PROPOSED_SIZE_NOT_POSITIVE"),
        (Decimal("-0.01"), "PROPOSED_SIZE_NOT_POSITIVE"),
        (Decimal("0.505"), "PROPOSED_SIZE_OFF_STEP"),
    ],
)
def test_unsafe_proposed_sizes_are_denied(lots, reason):
    result = validate(lots)
    assert result.within_risk_limit is False
    assert result.reason_code == reason


@pytest.mark.parametrize("bad", [10000, 10000.0, "10000", None, Decimal("NaN"), Decimal("Infinity")])
def test_invalid_equity_is_denied(bad):
    result = validate(Decimal("0.50"), equity=bad)
    assert result.within_risk_limit is False
    assert result.reason_code == "INVALID_DECIMAL_INPUT"


@pytest.mark.parametrize("bad", [100, 100.0, "100", None, Decimal("NaN"), Decimal("-Infinity")])
def test_invalid_stop_is_denied(bad):
    result = validate(Decimal("0.50"), stop=bad)
    assert result.within_risk_limit is False
    assert result.reason_code == "INVALID_DECIMAL_INPUT"


@pytest.mark.parametrize("bad", [1, 1.0, "1", None, Decimal("NaN"), Decimal("Infinity")])
def test_invalid_proposed_lots_are_denied(bad):
    result = validate(bad)
    assert result.within_risk_limit is False
    assert result.reason_code == "INVALID_DECIMAL_INPUT"


@pytest.mark.parametrize(
    ("equity", "stop"),
    [
        (Decimal("0"), Decimal("100")),
        (Decimal("-1"), Decimal("100")),
        (Decimal("10000"), Decimal("0")),
        (Decimal("10000"), Decimal("-1")),
    ],
)
def test_non_positive_equity_or_stop_is_denied(equity, stop):
    result = validate(Decimal("0.50"), equity=equity, stop=stop)
    assert result.within_risk_limit is False
    assert result.reason_code == "RISK_REVALIDATION_FAILED"


def test_wrong_spec_type_is_denied():
    result = revalidate_proposed_size(
        Decimal("10000"), Decimal("100"), Decimal("0.50"), spec=object()
    )
    assert result.within_risk_limit is False
    assert result.reason_code == "INVALID_RISK_SPEC"


def test_low_level_mutation_of_frozen_spec_is_denied():
    mutated = spec()
    object.__setattr__(mutated, "risk_fraction", Decimal("NaN"))
    result = validate(Decimal("0.50"), risk_spec=mutated)
    assert result.within_risk_limit is False
    assert result.reason_code == "INVALID_RISK_SPEC"


def test_non_step_aligned_broker_cap_is_denied():
    result = validate(
        Decimal("0.50"),
        risk_spec=spec(max_lot=Decimal("0.505")),
    )
    assert result.within_risk_limit is False
    assert result.reason_code == "INVALID_RISK_SPEC"


def test_decimal_context_failure_fails_closed():
    with localcontext() as context:
        context.prec = 2
        context.traps[Inexact] = True
        result = validate(
            Decimal("10000"),  # proposed_lots
            equity=Decimal("12345"),
            stop=Decimal("37"),
        )
    assert result.within_risk_limit is False
    assert result.reason_code == "RISK_REVALIDATION_FAILED"


def test_inputs_are_not_mutated_and_result_is_immutable():
    risk_spec = spec()
    before = (
        risk_spec.risk_fraction,
        risk_spec.value_per_point_lot,
        risk_spec.lot_step,
        risk_spec.min_lot,
        risk_spec.max_lot,
    )
    result = validate(Decimal("0.50"), risk_spec=risk_spec)
    after = (
        risk_spec.risk_fraction,
        risk_spec.value_per_point_lot,
        risk_spec.lot_step,
        risk_spec.min_lot,
        risk_spec.max_lot,
    )
    assert before == after
    with pytest.raises((AttributeError, TypeError)):
        result.within_risk_limit = False


def test_result_is_deterministic():
    args = (Decimal("10000"), Decimal("100"), Decimal("0.75"))
    first = revalidate_proposed_size(*args, spec=spec())
    second = revalidate_proposed_size(*args, spec=spec())
    assert first == second
