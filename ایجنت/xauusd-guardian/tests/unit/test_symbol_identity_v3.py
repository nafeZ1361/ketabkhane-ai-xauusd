"""D-003 implementation — exact identity plus metadata corroboration (v3)."""

from __future__ import annotations

from dataclasses import replace

from guardian.contracts.schemas import ResolutionStatus, SymbolSpec
from guardian.domain.symbols import (
    IDENTITY_POLICY,
    GoldExpectations,
    identify_gold_symbol,
)


def _resolve(symbols, **kwargs):
    return identify_gold_symbol(symbols, policy=IDENTITY_POLICY, account_currency="USD", **kwargs)


def test_identity_verifies_the_real_symbol(captured_symbols):
    result = _resolve(captured_symbols)

    assert result.status is ResolutionStatus.VERIFIED
    assert result.ok is True
    assert result.symbol_name == "XAUUSD."
    assert result.policy == IDENTITY_POLICY
    assert result.mismatches == ()


def test_identity_is_not_a_score_winner(captured_symbols):
    """The three other tie candidates must be irrelevant to the decision."""
    without_noise = [s for s in captured_symbols if s.name == "XAUUSD."]
    result = _resolve(without_noise)
    assert result.status is ResolutionStatus.VERIFIED
    assert result.ranked == ()  # identity policy publishes no ranking


def test_missing_symbol_is_not_found_and_never_substituted():
    only_equity = [
        SymbolSpec(
            name="GOLD.",
            path=r"Pure\Shares\Shares USA\GOLD.",
            description="Barrick Gold Corp",
            trade_mode=4,
            digits=2,
            tick_size=0.01,
            contract_size=100.0,
            currency_base="USD",
            currency_profit="USD",
            visible=True,
        )
    ]
    result = _resolve(only_equity)

    assert result.status is ResolutionStatus.NOT_FOUND
    assert result.symbol_name is None
    assert "GOLD." not in (result.symbol_name or "")


def test_contract_mismatch_is_reported_with_both_values(captured_symbols):
    broken = [
        replace(spec, contract_size=10.0) if spec.name == "XAUUSD." else spec
        for spec in captured_symbols
    ]
    result = _resolve(broken)

    assert result.status is ResolutionStatus.METADATA_MISMATCH
    assert result.symbol_name == "XAUUSD."
    assert result.mismatches == (("contract_size", "100", "10"),)
    assert result.primary_mismatch[0] == "contract_size"


def test_path_class_mismatch_is_reported(captured_symbols):
    broken = [
        replace(spec, path=r"Pure\Shares\Shares USA\XAUUSD.") if spec.name == "XAUUSD." else spec
        for spec in captured_symbols
    ]
    result = _resolve(broken)

    assert result.status is ResolutionStatus.METADATA_MISMATCH
    assert result.mismatches[0][0] == "path"


def test_closed_trade_mode_is_a_mismatch(captured_symbols):
    broken = [replace(spec, trade_mode=3) if spec.name == "XAUUSD." else spec for spec in captured_symbols]
    result = _resolve(broken)

    assert result.status is ResolutionStatus.METADATA_MISMATCH
    assert ("trade_mode", "4", "3") in result.mismatches


def test_wrong_profit_currency_is_a_mismatch(captured_symbols):
    broken = [
        replace(spec, currency_profit="EUR") if spec.name == "XAUUSD." else spec
        for spec in captured_symbols
    ]
    result = _resolve(broken)

    assert result.status is ResolutionStatus.METADATA_MISMATCH
    assert result.mismatches[0][0] == "currency_profit"


def test_multiple_identity_matches_block(captured_symbols):
    target = next(s for s in captured_symbols if s.name == "XAUUSD.")
    wide = GoldExpectations(aliases=("XAUUSD", "XAUUSD."))
    result = _resolve(captured_symbols + [replace(target, name="XAUUSD")], expectations=wide)

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert result.symbol_name is None
    assert "XAUUSD" in result.reason


def test_bare_xauusd_is_not_found_by_default():
    bare = SymbolSpec(
        name="XAUUSD",
        path=r"Pure\Spot Metals\Gold\XAUUSD",
        trade_mode=4,
        digits=2,
        tick_size=0.01,
        contract_size=100.0,
        currency_profit="USD",
    )
    assert _resolve([bare]).status is ResolutionStatus.NOT_FOUND


def test_required_symbol_name_rejects_an_alias_variant():
    """A widened alias list must not silently accept a different instrument."""
    bare = SymbolSpec(
        name="XAUUSD",
        path=r"Pure\Spot Metals\Gold\XAUUSD",
        trade_mode=4,
        digits=2,
        tick_size=0.01,
        contract_size=100.0,
        currency_profit="USD",
    )
    wide = GoldExpectations(aliases=("XAUUSD", "XAUUSD."), required_symbol_name="XAUUSD.")
    result = _resolve([bare], expectations=wide)

    assert result.status is ResolutionStatus.METADATA_MISMATCH
    assert result.mismatches[0] == ("symbol_name", "XAUUSD.", "XAUUSD")


def test_matching_is_exact_and_case_insensitive(captured_symbols):
    lowered = [
        replace(spec, name="xauusd.") if spec.name == "XAUUSD." else spec for spec in captured_symbols
    ]
    result = _resolve(lowered)

    assert result.status is ResolutionStatus.VERIFIED
    assert result.symbol_name == "xauusd."


def test_aliases_are_configurable():
    custom = SymbolSpec(
        name="GOLDX",
        path=r"Pure\Spot Metals\Gold\GOLDX",
        trade_mode=4,
        digits=2,
        tick_size=0.01,
        contract_size=100.0,
        currency_profit="USD",
    )
    result = _resolve([custom], expectations=GoldExpectations(aliases=("GOLDX",)))

    assert result.status is ResolutionStatus.VERIFIED
    assert result.symbol_name == "GOLDX"


def test_optional_checks_can_be_disabled_but_identity_cannot():
    custom = SymbolSpec(
        name="XAUUSD.",
        path=r"Pure\Spot Metals\Gold\XAUUSD.",
        trade_mode=4,
        digits=2,
        tick_size=0.01,
        contract_size=1.0,
        currency_profit="USD",
    )
    lenient = GoldExpectations(contract_size=None, tick_size=None, digits=None)
    assert _resolve([custom], expectations=lenient).status is ResolutionStatus.VERIFIED

    strict = GoldExpectations()
    assert _resolve([custom], expectations=strict).status is ResolutionStatus.METADATA_MISMATCH


def test_observed_metadata_is_attached_as_evidence(captured_symbols):
    result = _resolve(captured_symbols)
    observed = dict(result.observed)

    assert observed["name"] == "XAUUSD."
    assert observed["path"] == r"Pure\Spot Metals\Gold\XAUUSD."
    assert observed["contract_size"] == "100"
    assert observed["trade_mode"] == "4"
    assert observed["stops_level"] == "10"


def test_empty_expectations_cannot_resolve():
    result = _resolve([], expectations=GoldExpectations(aliases=()))
    assert result.status is ResolutionStatus.NOT_FOUND
    assert "refusing to guess" in result.reason
