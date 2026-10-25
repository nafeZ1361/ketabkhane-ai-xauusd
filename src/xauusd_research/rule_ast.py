"""Rule-AST layer (R1): serializable strategy trees, blueprint sections B/C/D.

Governing docs: Charter v2.0 section 14 (research/paper only), ADL-006
(SQX_BLUEPRINT as design reference), ADL-007 (stdlib-only research factory).

Design invariants (acceptance tests AT-R1-*):
- Every node is a frozen dataclass; the whole tree round-trips through
  JSON with byte-identical hashes (reproducibility: seed + config hash).
- Evaluation is strictly causal: an indicator at bar i may only use bars
  <= i (no look-ahead / leakage by construction).
- Unknown field or out-of-range parameter => rejection, never a guess
  (same philosophy as costs.UnknownSpecError, ADL-004).
"""

from __future__ import annotations

import hashlib
import json

MAX_TREE_DEPTH = 6
MAX_CONDITIONS_PER_RULE = 8


class RuleSpecError(ValueError):
    """Raised when a rule tree is unknown, malformed or out of range."""


# ---------------------------------------------------------------------------
# Indicator specs (building blocks, blueprint layer 2)
# ---------------------------------------------------------------------------

INDICATOR_RANGES = {
    "sma": (2, 500),
    "ema": (2, 500),
    "rsi": (2, 100),
    "atr": (2, 200),
    "donchian": (2, 500),
}
PRICE_FIELDS = ("open", "high", "low", "close")
COMPARATORS = (">", "<", ">=", "<=")


def _check_indicator(name, window):
    if name not in INDICATOR_RANGES:
        raise RuleSpecError(f"unknown indicator: {name!r}")
    lo, hi = INDICATOR_RANGES[name]
    if not isinstance(window, int) or not (lo <= window <= hi):
        raise RuleSpecError(f"{name} window {window!r} outside [{lo},{hi}]")
    return {"kind": name, "window": window}


class Ind:
    """Indicator reference node: value of `kind` at bar i (causal)."""

    def __init__(self, kind, window, offset=0):
        self.spec = _check_indicator(kind, window)
        if not isinstance(offset, int) or not (0 <= offset <= 10):
            raise RuleSpecError(f"offset must be int in [0,10], got {offset!r}")
        self.kind = self.spec["kind"]
        self.window = self.spec["window"]
        self.offset = offset

    @property
    def key(self):
        return (self.kind, self.window)

    def to_dict(self):
        return {"t": "ind", "kind": self.kind, "window": self.window,
                "offset": self.offset}


class Price:
    """Raw price field reference at bar i - offset (causal)."""

    def __init__(self, field, offset=0):
        if field not in PRICE_FIELDS:
            raise RuleSpecError(f"unknown price field: {field!r}")
        if not isinstance(offset, int) or not (0 <= offset <= 10):
            raise RuleSpecError(f"offset must be int in [0,10], got {offset!r}")
        self.field = field
        self.offset = offset

    def to_dict(self):
        return {"t": "price", "field": self.field, "offset": self.offset}


class Const:
    def __init__(self, value):
        if not isinstance(value, (int, float)):
            raise RuleSpecError("const must be numeric")
        self.value = float(value)

    def to_dict(self):
        return {"t": "const", "value": self.value}


# ---------------------------------------------------------------------------
# Boolean expression nodes
# ---------------------------------------------------------------------------

class Compare:
    """Leaf predicate: lhs comparator rhs (both are value nodes)."""

    def __init__(self, lhs, op, rhs):
        if op not in COMPARATORS:
            raise RuleSpecError(f"unknown comparator: {op!r}")
        for side in (lhs, rhs):
            if not isinstance(side, (Ind, Price, Const)):
                raise RuleSpecError("compare operands must be Ind/Price/Const")
        if isinstance(lhs, Const) and isinstance(rhs, Const):
            raise RuleSpecError("constant-vs-constant comparison is meaningless")
        self.lhs, self.op, self.rhs = lhs, op, rhs

    def indicators(self):
        out = []
        for side in (self.lhs, self.right_operand()):
            if isinstance(side, Ind):
                out.append(side)
        return out

    def right_operand(self):
        return self.rhs

    def to_dict(self):
        return {"t": "cmp", "op": self.op,
                "lhs": _val_to_dict(self.lhs), "rhs": _val_to_dict(self.rhs)}


class Logic:
    """AND/OR/NOT over boolean nodes."""

    def __init__(self, op, *children):
        if op not in ("and", "or", "not"):
            raise RuleSpecError(f"unknown logic op: {op!r}")
        if op == "not" and len(children) != 1:
            raise RuleSpecError("not takes exactly one child")
        if op in ("and", "or") and not (1 <= len(children) <= MAX_CONDITIONS_PER_RULE):
            raise RuleSpecError(
                f"{op} needs 1..{MAX_CONDITIONS_PER_RULE} children")
        for c in children:
            if not isinstance(c, (Compare, Logic)):
                raise RuleSpecError("logic children must be Compare/Logic")
        self.op, self.children = op, tuple(children)

    def to_dict(self):
        return {"t": "logic", "op": self.op,
                "children": [_bool_to_dict(c) for c in self.children]}


def _val_to_dict(node):
    return node.to_dict()


def _bool_to_dict(node):
    return node.to_dict()


# ---------------------------------------------------------------------------
# Exit rules and the strategy root
# ---------------------------------------------------------------------------

class ExitRule:
    """Fixed exit relative to entry price: sl/tp as positive fraction."""

    def __init__(self, stop_loss_pct=None, take_profit_pct=None, max_bars=None):
        for name, val in (("stop_loss_pct", stop_loss_pct),
                          ("take_profit_pct", take_profit_pct)):
            if val is not None:
                if not isinstance(val, (int, float)) or not (0.0 < val <= 0.20):
                    raise RuleSpecError(f"{name} must be in (0, 0.20], got {val!r}")
        if max_bars is not None:
            if not isinstance(max_bars, int) or not (1 <= max_bars <= 100000):
                raise RuleSpecError(f"max_bars must be int >= 1, got {max_bars!r}")
        if stop_loss_pct is None and take_profit_pct is None and max_bars is None:
            raise RuleSpecError("ExitRule needs at least one constraint")
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_bars = max_bars

    def to_dict(self):
        return {"stop_loss_pct": self.stop_loss_pct,
                "take_profit_pct": self.take_profit_pct,
                "max_bars": self.max_bars}


class RuleStrategy:
    """Root node: entry (long/short) boolean trees plus exits.

    direction: 'long' | 'short' | 'both'. With 'both', short_entry must be
    provided; otherwise it is ignored.
    """

    def __init__(self, name, long_entry, short_entry=None, direction="long",
                 exit_rule=None):
        if not isinstance(name, str) or not name.strip():
            raise RuleSpecError("strategy name required")
        if direction not in ("long", "short", "both"):
            raise RuleSpecError(f"unknown direction: {direction!r}")
        if direction in ("long", "both") and not isinstance(long_entry, (Compare, Logic)):
            raise RuleSpecError("long_entry must be a boolean node")
        if direction in ("short", "both") and not isinstance(short_entry, (Compare, Logic)):
            raise RuleSpecError(f"{direction} requires short_entry")
        if exit_rule is not None and not isinstance(exit_rule, ExitRule):
            raise RuleSpecError("exit_rule must be an ExitRule")
        self.name = name.strip()
        self.long_entry = long_entry
        self.short_entry = short_entry
        self.direction = direction
        self.exit_rule = exit_rule or ExitRule(max_bars=100)
        depth = max(_depth(self.long_entry, 1),
                    _depth(self.short_entry, 1) if self.short_entry else 0)
        if depth > MAX_TREE_DEPTH:
            raise RuleSpecError(
                f"tree depth {depth} exceeds MAX_TREE_DEPTH={MAX_TREE_DEPTH}")

    def to_dict(self):
        return {
            "schema": "rule-strategy/v1",
            "name": self.name,
            "direction": self.direction,
            "long_entry": _bool_to_dict(self.long_entry) if self.long_entry else None,
            "short_entry": _bool_to_dict(self.short_entry) if self.short_entry else None,
            "exit": self.exit_rule.to_dict(),
        }

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def config_hash(self):
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()

    def indicator_needs(self):
        """All (kind, window, offset) this strategy evaluates, deduped/sorted."""
        seen = {}
        for tree in filter(None, (self.long_entry, self.short_entry)):
            _collect(tree, seen)
        return sorted(seen.values(), key=lambda s: (s["kind"], s["window"], s["offset"]))


def _collect(node, out):
    if isinstance(node, Compare):
        for side in (node.lhs, node.rhs):
            if isinstance(side, Ind):
                out[(side.kind, side.window, side.offset)] = side.to_dict()
    elif isinstance(node, Logic):
        for c in node.children:
            _collect(c, out)


def _depth(node, current):
    if isinstance(node, Compare):
        return current
    if isinstance(node, Logic):
        return max((_depth(c, current + 1) for c in node.children), default=current)
    return current


# ---------------------------------------------------------------------------
# Deserialization (Databank reload path, blueprint layer 8)
# ---------------------------------------------------------------------------

def _val_from_dict(d):
    t = d.get("t")
    if t == "ind":
        return Ind(d["kind"], d["window"], d.get("offset", 0))
    if t == "price":
        return Price(d["field"], d.get("offset", 0))
    if t == "const":
        return Const(d["value"])
    raise RuleSpecError(f"unknown value node type: {t!r}")


def _bool_from_dict(d):
    t = d.get("t")
    if t == "cmp":
        return Compare(_val_from_dict(d["lhs"]), d["op"], _val_from_dict(d["rhs"]))
    if t == "logic":
        return Logic(d["op"], *[_bool_from_dict(c) for c in d["children"]])
    raise RuleSpecError(f"unknown boolean node type: {t!r}")


def strategy_from_dict(d):
    if d.get("schema") != "rule-strategy/v1":
        raise RuleSpecError(f"unsupported schema: {d.get('schema')!r}")
    ex = d.get("exit") or {}
    return RuleStrategy(
        name=d["name"],
        long_entry=_bool_from_dict(d["long_entry"]) if d.get("long_entry") else None,
        short_entry=_bool_from_dict(d["short_entry"]) if d.get("short_entry") else None,
        direction=d.get("direction", "long"),
        exit_rule=ExitRule(ex.get("stop_loss_pct"), ex.get("take_profit_pct"),
                           ex.get("max_bars")),
    )


def strategy_from_json(text):
    return strategy_from_dict(json.loads(text))
