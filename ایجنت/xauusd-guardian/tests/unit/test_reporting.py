"""Regression for audit finding 1: ranked entries are (score, name) and the
display must render them as ``name:score`` — never swapped.
"""

from __future__ import annotations

from guardian.contracts.schemas import RankedSymbol
from guardian.domain.symbols import STRICT_POLICY, identify_gold_symbol
from guardian.reporting.ranking import format_ranked


def test_format_renders_name_then_score():
    ranked: list[RankedSymbol] = [(6, "GOLD."), (5, "XAUXAG."), (2, "AronGold.")]
    assert format_ranked(ranked) == "GOLD.:6, XAUXAG.:5, AronGold.:2"


def test_format_honours_limit():
    ranked: list[RankedSymbol] = [(6, "A"), (5, "B"), (4, "C")]
    assert format_ranked(ranked, limit=2) == "A:6, B:5"


def test_format_handles_empty_ranking():
    assert format_ranked(()) == ""


def test_live_ranking_is_score_first_and_renders_correctly(captured_symbols):
    result = identify_gold_symbol(captured_symbols, policy=STRICT_POLICY)

    assert result.ranked, "strict policy must still publish a ranking"
    for score, name in result.ranked:
        assert isinstance(score, int)
        assert isinstance(name, str)

    rendered = format_ranked(result.ranked)
    assert rendered.startswith("GOLD.:6"), rendered
    assert "::" not in rendered
