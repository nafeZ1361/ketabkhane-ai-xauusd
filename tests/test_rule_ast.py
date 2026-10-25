"""R1 acceptance tests: rule AST, deterministic engine, seeded generator.

AT-R1-roundtrip   JSON serialization is byte-stable and hash-reproducible.
AT-R1-guards      malformed/out-of-range trees are rejected, never guessed.
AT-R1-causality   signal at bar i uses only bars <= i; fills at i+1 open.
AT-R1-determinism same candles+strategy => identical trades/equity twice.
AT-R1-seed        same seed => thousands of identical strategies (exit gate H).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from xauusd_research.rule_ast import (Compare, Const, ExitRule, Ind, Logic,
                                      Price, RuleSpecError, RuleStrategy,
                                      strategy_from_json)
from xauusd_research.rule_engine import (build_series, eval_bool,
                                        rule_signals, run_rule_backtest)
from xauusd_research.rule_generator import generate_batch, generate_strategy
from xauusd_research.schema import load_candles

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_500.csv"


def make_strategy():
    long_entry = Logic("and",
                       Compare(Ind("sma", 3), ">", Ind("sma", 8)),
                       Compare(Price("close"), "<", Ind("donchian", 2)))
    short_entry = Compare(Logic("not", Compare(Ind("rsi", 3), ">", Const(70.0))),
                          "__never__", Const(0.0)) if False else \
        Compare(Ind("rsi", 3), "<", Const(30.0))
    return RuleStrategy("unit_test_strategy", long_entry, short_entry,
                        direction="both",
                        exit_rule=ExitRule(stop_loss_pct=0.01,
                                           take_profit_pct=0.02, max_bars=20))


# ---------------------------------------------------------------------------
# AT-R1-roundtrip / guards
# ---------------------------------------------------------------------------

def test_roundtrip_hash_stable():
    s = make_strategy()
    js = s.to_json()
    again = strategy_from_json(js)
    assert again.config_hash() == s.config_hash()
    assert again.to_json() == js
    parsed = json.loads(js)
    assert parsed["schema"] == "rule-strategy/v1"
    assert parsed["direction"] == "both"


def test_unknown_indicator_rejected():
    with pytest.raises(RuleSpecError):
        Ind("macd_magic", 12)


def test_window_out_of_range_rejected():
    with pytest.raises(RuleSpecError):
        Ind("sma", 9999)
    with pytest.raises(RuleSpecError):
        ExitRule(stop_loss_pct=0.5)  # > 0.20 bound


def test_const_vs_const_rejected():
    with pytest.raises(RuleSpecError):
        Compare(Const(1.0), ">", Const(2.0))


def test_depth_guard():
    node = Compare(Ind("sma", 2), ">", Const(0.0))
    for _ in range(10):
        node = Logic("and", node)
    with pytest.raises(RuleSpecError):
        RuleStrategy("too_deep", node, None, "long")


# ---------------------------------------------------------------------------
# AT-R1-causality / determinism
# ---------------------------------------------------------------------------

def candles():
    return load_candles(FIXTURE)


def test_signals_are_causal():
    cs = candles()
    s = make_strategy()
    full_sig = rule_signals(cs, s)
    # Truncating the future must not change any past signal.
    for cut in (len(cs) - 1, len(cs) // 2, 60):
        partial = rule_signals(cs[:cut], s)
        assert partial[:min(cut, len(full_sig))] == full_sig[:cut]


def test_next_bar_fill_no_lookahead():
    cs = candles()
    s = make_strategy()
    res = run_rule_backtest(cs, s)
    sig = rule_signals(cs, s)
    times = [c.time for c in cs]
    for t in res.trades:
        idx = times.index(t.entry_time)
        assert idx >= 1
        assert sig[idx - 1] != 0  # entry follows a signal strictly earlier


def test_deterministic_double_run():
    cs = candles()
    s = make_strategy()
    a = run_rule_backtest(cs, s)
    b = run_rule_backtest(cs, s)
    assert [t.__dict__ | {"time": str(t.entry_time)} for t in a.trades] == \
           [t.__dict__ | {"time": str(t.entry_time)} for t in b.trades]
    assert a.equity == b.equity
    assert a.metrics == b.metrics


def test_stop_loss_bounds_pnl():
    cs = candles()
    s = RuleStrategy("sl_probe",
                     Compare(Price("close", 0), ">", Const(-1.0)),  # always true
                     None, "long",
                     ExitRule(stop_loss_pct=0.01, max_bars=None))
    # Use tiny windows warmup-free: close > -1 always true from bar 0.
    res = run_rule_backtest(cs, s)
    closes = [c.close for c in cs]
    for t in res.trades:
        # price move beyond SL% cannot exceed ~SL plus one bar gap (pessimistic fill at level)
        worst = -(max(closes) * 0.05)
        assert t.pnl >= worst
        assert t.reason in ("stop_loss", "end_of_data")


def test_warmup_blocks_early_entries():
    cs = candles()
    s = RuleStrategy("big_window",
                     Compare(Ind("sma", 55), ">", Ind("ema", 55)),
                     None, "long", ExitRule(max_bars=10))
    sig = rule_signals(cs, s)
    assert all(v == 0 for v in sig[:54])  # no signal before warmup completes


# ---------------------------------------------------------------------------
# AT-R1-seed (phase R1 exit gate: stable generation of thousands)
# ---------------------------------------------------------------------------

def test_seed_reproducibility_thousands():
    batch_a = generate_batch(seed=42, count=2000)
    batch_b = generate_batch(seed=42, count=2000)
    hashes_a = [g.config_hash() for g in batch_a]
    hashes_b = [g.config_hash() for g in batch_b]
    assert hashes_a == hashes_b
    assert len(set(hashes_a)) > 1500  # genuine diversity, not degenerate repeats


def test_different_seeds_diverge():
    a = {g.config_hash() for g in generate_batch(seed=1, count=100)}
    b = {g.config_hash() for g in generate_batch(seed=2, count=100)}
    assert not (a & b)


def test_generated_strategies_evaluate_on_fixture():
    cs = candles()
    for g in generate_batch(seed=7, count=25):
        res = run_rule_backtest(cs, g)  # must not raise
        assert isinstance(res.metrics["trades"], int)
