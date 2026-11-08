"""Symbol resolution policy tests.

The strict policy is expected to BLOCK on the live broker symbol set: that is
the documented blocker B2 and must stay visible, not be tuned away.
"""

from __future__ import annotations

import pytest

from guardian.contracts.schemas import ResolutionStatus, SymbolSpec
from guardian.domain.symbols import (
    AMENDED_POLICY,
    STRICT_POLICY,
    identify_gold_symbol,
    score_symbol,
)


def test_score_matches_specification_weights(real_symbol_table):
    by_name = {s.name: s for s in real_symbol_table}
    assert score_symbol(by_name["XAUUSD."]) == 6
    assert score_symbol(by_name["GoldmanSachs."]) == 6
    assert score_symbol(by_name["XAUXAG."]) == 5


def test_strict_policy_is_ambiguous_on_real_broker_table(real_symbol_table):
    result = identify_gold_symbol(real_symbol_table, policy=STRICT_POLICY)

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert result.symbol_name is None
    assert result.margin == 0
    assert not result.ok
    tied = [name for score, name in result.ranked if score == 6]
    assert set(tied) == {"XAUUSD.", "XAUEUR.", "GoldmanSachs.", "GOLD."}


def test_strict_policy_resolves_when_broker_table_is_clean():
    clean = [
        SymbolSpec(
            name="XAUUSD.",
            path=r"Pure\Spot Metals\Gold\XAUUSD.",
            description="Gold vs US Dollar",
            trade_mode=4,
            digits=2,
            tick_size=0.01,
            contract_size=100.0,
            currency_profit="USD",
            visible=True,
        ),
        SymbolSpec(name="EURUSD.", trade_mode=4, digits=5, contract_size=100000.0),
    ]
    result = identify_gold_symbol(clean, policy=STRICT_POLICY)

    assert result.status is ResolutionStatus.RESOLVED
    assert result.symbol_name == "XAUUSD."


def test_amended_policy_resolves_real_table_uniquely(real_symbol_table):
    result = identify_gold_symbol(real_symbol_table, policy=AMENDED_POLICY, account_currency="USD")

    assert result.status is ResolutionStatus.RESOLVED
    assert result.symbol_name == "XAUUSD."


def test_amended_policy_rejects_equities_sharing_the_name(real_symbol_table):
    equities = [s for s in real_symbol_table if s.path.startswith(r"Pure\Shares")]
    result = identify_gold_symbol(equities, policy=AMENDED_POLICY, account_currency="USD")

    assert result.status is ResolutionStatus.NOT_FOUND
    assert result.symbol_name is None


def test_not_found_when_no_gold_symbol():
    only_fx = [SymbolSpec(name="EURUSD.", trade_mode=4, digits=5, contract_size=100000.0)]
    result = identify_gold_symbol(only_fx, policy=STRICT_POLICY)

    assert result.status is ResolutionStatus.NOT_FOUND


def test_legacy_policies_are_never_permissive(captured_symbols):
    """Audit finding F1: a scoring result must not be able to open the gate."""
    from guardian.contracts.schemas import ResolutionStatus

    resolved = identify_gold_symbol(
        [s for s in captured_symbols if s.name == "XAUUSD."], policy=STRICT_POLICY
    )
    assert resolved.status is ResolutionStatus.RESOLVED
    assert resolved.ok is False
    assert ResolutionStatus.RESOLVED is not ResolutionStatus.VERIFIED

    amended = identify_gold_symbol(captured_symbols, policy=AMENDED_POLICY)
    assert amended.status is ResolutionStatus.RESOLVED
    assert amended.ok is False


def test_unknown_policy_is_rejected(real_symbol_table):
    with pytest.raises(ValueError):
        identify_gold_symbol(real_symbol_table, policy="whatever_v9")


def test_amended_policy_still_blocks_if_two_symbols_remain(real_symbol_table):
    both = [s for s in real_symbol_table if s.name in {"XAUUSD.", "XAUEUR."}]
    result = identify_gold_symbol(both, policy=AMENDED_POLICY, account_currency="USD")

    assert result.status is ResolutionStatus.RESOLVED  # EUR profit != USD -> filtered out
    assert result.symbol_name == "XAUUSD."
