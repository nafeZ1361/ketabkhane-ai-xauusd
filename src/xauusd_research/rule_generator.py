"""Seeded random strategy generator (R1): blueprint layer 3, phase R1 exit gate.

Governing docs: ADL-006/ADL-007, SQX_BLUEPRINT sections D (steps 3-5) and K
("reproducibility: store seed, data version, config hash").

Exit criterion for phase R1 (blueprint section H): "stable generation of
thousands of strategies" — determinism is the hard requirement: same seed +
same config => byte-identical JSON trees, verified by test AT-R1-seed.
"""

from __future__ import annotations

import random

from .rule_ast import (INDICATOR_RANGES, Compare, Const, ExitRule, Ind,
                       Logic, Price, RuleStrategy, RuleSpecError)

# Windows deliberately small so generated trees are evaluable on fixtures
# while staying inside INDICATOR_RANGES (validated again by rule_ast).
WINDOWS = (2, 3, 5, 8, 13, 21, 34, 55)
KINDS = tuple(sorted(INDICATOR_RANGES))


def _pick_window(rng, kind):
    lo, hi = INDICATOR_RANGES[kind]
    choices = [w for w in WINDOWS if lo <= w <= hi]
    return rng.choice(choices)


def _value_node(rng, allow_ind=True):
    roll = rng.random()
    if roll < 0.45 and allow_ind:
        kind = rng.choice(KINDS)
        return Ind(kind, _pick_window(rng, kind), rng.randint(0, 2))
    if roll < 0.75:
        return Price(rng.choice(("open", "high", "low", "close")),
                     rng.randint(0, 3))
    return Const(round(rng.uniform(0.5, 3.0), 4))


def _compare(rng):
    lhs = _value_node(rng)
    rhs = _value_node(rng, allow_ind=True)
    if isinstance(lhs, Const) and isinstance(rhs, Const):
        rhs = Price("close", 0)
    return Compare(lhs, rng.choice((">", "<")), rhs)


def _entry_tree(rng, max_conditions=3):
    n = rng.randint(1, max_conditions)
    preds = [_compare(rng) for _ in range(n)]
    if n == 1:
        return preds[0]
    tree = Logic("and", *preds)
    if rng.random() < 0.25:
        tree = Logic("or", tree, _compare(rng))
    return tree


def generate_strategy(seed, index=0, direction=None, max_conditions=3):
    """Deterministic strategy from (seed, index). Same inputs => same tree."""
    rng = random.Random(f"{seed}:{index}")
    direction = direction or rng.choice(("long", "short", "both"))
    long_entry = _entry_tree(rng, max_conditions) if direction in ("long", "both") else None
    short_entry = _entry_tree(rng, max_conditions) if direction in ("short", "both") else None
    if direction == "short":
        long_entry = None
    elif direction == "long":
        short_entry = None
    exit_rule = ExitRule(
        stop_loss_pct=round(rng.uniform(0.001, 0.02), 4),
        take_profit_pct=round(rng.uniform(0.002, 0.04), 4),
        max_bars=rng.choice((10, 25, 50, 100)),
    )
    try:
        return RuleStrategy(f"gen_{seed}_{index}", long_entry, short_entry,
                            direction, exit_rule)
    except RuleSpecError:
        # Structural guard failed (e.g. depth); retry with a flat AND tree.
        flat = Logic("and", *[_compare(rng) for _ in range(2)])
        return RuleStrategy(f"gen_{seed}_{index}", flat, None, "long", exit_rule)


def generate_batch(seed, count, **kwargs):
    """Batch generator; hashes are stable across calls for the same seed."""
    return [generate_strategy(seed, i, **kwargs) for i in range(count)]
