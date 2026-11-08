"""D-003 investigation tests — read-only, fixture-driven.

These tests prove the ambiguity is real, that it is a property of the scoring
rule and not of the data, and that the surviving discriminators are the
documented ones. They do not change any production module.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from guardian.contracts.schemas import ResolutionStatus, SymbolSpec
from guardian.domain.symbols import (
    AMENDED_POLICY,
    STRICT_POLICY,
    identify_gold_symbol,
    score_symbol,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "gold_candidates_20261104.json"

#: Fixture keeps verbatim MT5 field names; SymbolSpec uses short domain names.
_MT5_TO_SPEC = {
    "name": "name",
    "path": "path",
    "description": "description",
    "trade_mode": "trade_mode",
    "digits": "digits",
    "point": "point",
    "trade_tick_size": "tick_size",
    "trade_tick_value": "tick_value",
    "trade_contract_size": "contract_size",
    "volume_min": "volume_min",
    "volume_max": "volume_max",
    "volume_step": "volume_step",
    "trade_stops_level": "stops_level",
    "trade_freeze_level": "freeze_level",
    "filling_mode": "filling_mode",
    "currency_base": "currency_base",
    "currency_profit": "currency_profit",
    "visible": "visible",
}


def _to_spec(row: dict) -> SymbolSpec:
    return SymbolSpec(**{spec_key: row[mt5_key] for mt5_key, spec_key in _MT5_TO_SPEC.items()})


@pytest.fixture(scope="module")
def captured() -> list[SymbolSpec]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [_to_spec(row) for row in payload["symbols"]]


def _by_name(captured: list[SymbolSpec]) -> dict[str, SymbolSpec]:
    return {s.name: s for s in captured}


def test_captured_metadata_is_complete(captured):
    assert len(captured) == 5
    assert set(_by_name(captured)) == {"XAUUSD.", "XAUEUR.", "GOLD.", "GoldmanSachs.", "XAUXAG."}
    for spec in captured:
        assert spec.contract_size > 0
        assert spec.path and spec.description and spec.currency_profit


def test_target_symbol_metadata(captured):
    target = _by_name(captured)["XAUUSD."]
    assert target.path == r"Pure\Spot Metals\Gold\XAUUSD."
    assert target.currency_base == "USD"  # NOT "XAU" — the dead weight
    assert target.currency_profit == "USD"
    assert target.contract_size == 100.0
    assert target.tick_size == 0.01
    assert target.digits == 2
    assert target.trade_mode == 4


def test_four_way_tie_is_reproducible(captured):
    result = identify_gold_symbol(captured, policy=STRICT_POLICY)

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert result.margin == 0
    tied = sorted(name for score, name in result.ranked if score == 6)
    assert tied == ["GOLD.", "GoldmanSachs.", "XAUEUR.", "XAUUSD."]
    assert all(score_symbol(_by_name(captured)[n]) == 6 for n in tied)


def test_equities_are_indistinguishable_from_gold_under_the_rule(captured):
    table = _by_name(captured)
    assert score_symbol(table["XAUUSD."]) == score_symbol(table["GOLD."]) == score_symbol(table["GoldmanSachs."])
    # Same contract, same tick, same digits: the numeric weights cannot separate them.
    for name in ("GOLD.", "GoldmanSachs."):
        assert table[name].contract_size == table["XAUUSD."].contract_size
        assert table[name].tick_size == table["XAUUSD."].tick_size
        assert table[name].digits == table["XAUUSD."].digits


def test_base_currency_weight_only_fires_on_the_disabled_cross(captured):
    table = _by_name(captured)
    base_xau = [s.name for s in captured if s.currency_base.upper() == "XAU"]
    assert base_xau == ["XAUXAG."]
    assert table["XAUXAG."].trade_mode == 0  # disabled, cannot be the target


def test_spot_metal_class_excludes_the_equities(captured):
    result = identify_gold_symbol(captured, policy=AMENDED_POLICY, account_currency="USD")

    assert result.status is ResolutionStatus.RESOLVED
    assert result.symbol_name == "XAUUSD."


def test_visibility_is_not_used_as_identity(captured):
    """An invisible XAUUSD. must still resolve: visibility is a terminal UI state."""
    hidden = [replace(spec, visible=False) if spec.name == "XAUUSD." else spec for spec in captured]
    assert _by_name(hidden)["XAUUSD."].visible is False
    result = identify_gold_symbol(hidden, policy=AMENDED_POLICY, account_currency="USD")
    assert result.symbol_name == "XAUUSD."


def test_two_identity_matches_block_instead_of_guessing(captured):
    """If a broker ever exposes both XAUUSD and XAUUSD., the resolver must block."""
    target = _by_name(captured)["XAUUSD."]
    duplicate = replace(target, name="XAUUSD")
    result = identify_gold_symbol(captured + [duplicate], policy=AMENDED_POLICY, account_currency="USD")

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert result.symbol_name is None


def test_empty_table_is_not_found(captured):
    result = identify_gold_symbol([], policy=STRICT_POLICY)
    assert result.status is ResolutionStatus.NOT_FOUND


def test_choosing_the_wrong_candidate_changes_broker_constraints(captured):
    """Evidence of impact: the four tied candidates are not interchangeable."""
    table = _by_name(captured)
    assert table["XAUUSD."].stops_level == 10
    assert table["XAUEUR."].stops_level == 20
    assert table["GoldmanSachs."].stops_level == 41
    assert table["XAUEUR."].currency_profit == "EUR"
