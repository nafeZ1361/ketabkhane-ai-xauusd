"""Phase 4 risk sizing — the pre-registered gates from D-023.

S1 risk bound · S2 step/cap · S3 monotonicity · S4 fail-closed matrix ·
S5 no trading surface · (S6 suite/compileall runs outside this file).
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from guardian.domain.risk import RiskError, RiskSpec, position_size

MODULE_DIR = Path(__file__).resolve().parents[2] / "src" / "guardian" / "domain" / "risk"

D01 = Decimal("0.01")
D1 = Decimal("1")


def spec(**overrides: Decimal) -> RiskSpec:
    base = dict(
        risk_fraction=D01,
        value_per_point_lot=D1,
        lot_step=D01,
        min_lot=D01,
        max_lot=Decimal("100"),
    )
    base.update(overrides)
    return RiskSpec(**base)


def test_exact_sizing() -> None:
    # 10 000 × 1 % = 100 risk; 100 points × 1.00 per point = 100 per lot → 1.00 lot.
    assert position_size(Decimal("10000"), Decimal("100"), spec()) == Decimal("1.00")


def test_rounds_down_to_lot_step() -> None:
    # 100 / 150 = 0.666… → floored to the 0.01 step.
    assert position_size(Decimal("10000"), Decimal("150"), spec()) == Decimal("0.66")


def test_result_never_exceeds_max_lot() -> None:
    clamped = spec(max_lot=Decimal("0.50"))
    assert position_size(Decimal("10000"), Decimal("100"), clamped) == Decimal("0.50")


def test_below_min_lot_fails_closed() -> None:
    with pytest.raises(RiskError, match="below min_lot|below one lot step"):
        position_size(Decimal("1"), Decimal("5000"), spec())


@pytest.mark.parametrize("equity", [Decimal("0"), Decimal("-1"), Decimal("-0.0001")])
def test_non_positive_equity_refused(equity: Decimal) -> None:
    with pytest.raises(RiskError):
        position_size(equity, Decimal("100"), spec())


@pytest.mark.parametrize("stop", [Decimal("0"), Decimal("-5")])
def test_non_positive_stop_refused(stop: Decimal) -> None:
    with pytest.raises(RiskError):
        position_size(Decimal("10000"), stop, spec())


@pytest.mark.parametrize("bad", [10000, 10000.0, "10000", None])
def test_non_decimal_equity_refused(bad: object) -> None:
    with pytest.raises(RiskError, match="must be Decimal"):
        position_size(bad, Decimal("100"), spec())  # type: ignore[arg-type]


def test_non_finite_values_refused() -> None:
    for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(RiskError):
            position_size(bad, Decimal("100"), spec())
        with pytest.raises(RiskError):
            position_size(Decimal("10000"), bad, spec())


@pytest.mark.parametrize(
    "overrides",
    [
        {"risk_fraction": Decimal("0")},
        {"risk_fraction": Decimal("1")},
        {"risk_fraction": Decimal("-0.01")},
        {"risk_fraction": Decimal("1.5")},
        {"value_per_point_lot": Decimal("0")},
        {"value_per_point_lot": Decimal("-1")},
        {"lot_step": Decimal("0")},
        {"min_lot": Decimal("0")},
        {"max_lot": Decimal("0.001")},          # below min_lot
        {"min_lot": Decimal("0.015")},          # not a multiple of lot_step
    ],
)
def test_inconsistent_spec_refused(overrides: dict) -> None:
    with pytest.raises(RiskError):
        spec(**overrides)


def test_risk_bound_holds_over_a_grid() -> None:
    equities = [Decimal(v) for v in ("500", "1000", "25000", "100000")]
    stops = [Decimal(v) for v in ("10", "25", "100", "333", "1000")]
    fractions = [Decimal(v) for v in ("0.001", "0.005", "0.01", "0.02")]
    checked = 0
    for equity in equities:
        for stop in stops:
            for fraction in fractions:
                current = spec(risk_fraction=fraction)
                try:
                    lots = position_size(equity, stop, current)
                except RiskError:
                    continue
                checked += 1
                risk_taken = lots * stop * current.value_per_point_lot
                assert risk_taken <= equity * fraction, (equity, stop, fraction, lots)
                assert lots > 0
                assert lots % current.lot_step == 0
                assert current.min_lot <= lots <= current.max_lot
    assert checked > 40  # the grid is real, not empty


def test_monotonic_in_risk_fraction() -> None:
    previous = Decimal("0")
    for fraction in ("0.001", "0.002", "0.005", "0.01", "0.02", "0.05"):
        lots = position_size(Decimal("50000"), Decimal("250"), spec(risk_fraction=Decimal(fraction)))
        assert lots >= previous
        previous = lots


def test_monotonic_inverse_in_stop_distance() -> None:
    previous = None
    for stop in ("10", "25", "50", "100", "200", "500"):
        lots = position_size(Decimal("50000"), Decimal(stop), spec())
        if previous is not None:
            assert lots <= previous
        previous = lots


def test_deterministic() -> None:
    args = (Decimal("12345.67"), Decimal("87"), spec())
    assert position_size(*args) == position_size(*args)


def test_module_has_no_trading_surface() -> None:
    forbidden_calls = {
        "order_send",
        "order_check",
        "account_info",
        "positions_get",
        "orders_get",
        "history_deals_get",
        "symbol_info_tick",
        "initialize",
    }
    allowed_imports = {"__future__", "dataclasses", "decimal"}
    sources = sorted(MODULE_DIR.glob("*.py"))
    assert sources, "risk package not found"
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in allowed_imports, (path.name, alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue  # package-relative import (e.g. ``from .sizing import ...``)
                root = (node.module or "").split(".")[0]
                assert root in allowed_imports | {""}, (path.name, node.module)
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert name not in forbidden_calls, (path.name, name)
            elif isinstance(node, ast.Name):
                assert node.id not in {"MetaTrader5", "mt5"}, (path.name, node.id)
            elif isinstance(node, ast.Attribute):
                assert node.attr not in {"MetaTrader5", "mt5"}, (path.name, node.attr)
        text = path.read_text(encoding="utf-8-sig")
        assert "guardian.adapters" not in text


def test_unaligned_max_lot_is_floored_to_valid_step() -> None:
    # 0.505 is a ceiling, not a valid volume for a 0.01 step.
    capped = spec(max_lot=Decimal("0.505"))
    lots = position_size(Decimal("10000"), Decimal("1"), capped)
    assert lots == Decimal("0.50")
    assert lots % capped.lot_step == 0
    assert lots <= capped.max_lot


def test_unaligned_max_lot_never_breaks_risk_bound() -> None:
    capped = spec(
        risk_fraction=Decimal("0.02"),
        value_per_point_lot=Decimal("10"),
        lot_step=Decimal("0.01"),
        max_lot=Decimal("0.505"),
    )
    lots = position_size(Decimal("10000"), Decimal("100"), capped)
    assert lots == Decimal("0.20")
    assert lots % capped.lot_step == 0
    assert lots * Decimal("100") * capped.value_per_point_lot <= Decimal("10000") * capped.risk_fraction
