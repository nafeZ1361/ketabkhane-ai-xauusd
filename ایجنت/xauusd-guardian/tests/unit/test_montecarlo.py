"""Monte Carlo risk engine — the pre-registered gates from D-026."""

from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from guardian.domain.risk.montecarlo import (
    MonteCarloError,
    MonteCarloSpec,
    _sample_block,
    canonical_digest,
    compare_strategies,
    sensitivity,
    simulate,
)

D = Decimal
ROOT = Path(__file__).resolve().parents[2]


def spec(**overrides: object) -> MonteCarloSpec:
    base = dict(
        simulations=200,
        seed=7,
        mode="iid",
        block_size=3,
        initial_equity=D("10000"),
        risk_fraction=D("0.01"),
        ruin_fraction=D("0.5"),
        cost_r=D("0"),
        cost_multiplier=D("1"),
        dd_thresholds=(D("0.05"), D("0.10"), D("0.20")),
    )
    base.update(overrides)
    return MonteCarloSpec(**base)  # type: ignore[arg-type]


TRADES = [D("1.5"), D("-1.0"), D("0.8"), D("-1.0"), D("2.0"), D("-0.5")] * 4


# ---------------------------------------------------------------- determinism
def test_same_seed_is_byte_identical() -> None:
    first = simulate(TRADES, spec())
    second = simulate(TRADES, spec())
    assert first.as_dict() == second.as_dict()


def test_different_seed_changes_the_sample() -> None:
    a = simulate(TRADES, spec(seed=1, simulations=500))
    b = simulate(TRADES, spec(seed=2, simulations=500))
    assert a.as_dict() != b.as_dict()


def test_iid_and_block_differ_on_the_same_seed() -> None:
    iid = simulate(TRADES, spec(mode="iid", simulations=300))
    block = simulate(TRADES, spec(mode="block", simulations=300))
    assert iid.as_dict() != block.as_dict()


# ---------------------------------------------------------------- block logic
def test_block_sampling_keeps_runs_contiguous() -> None:
    import random

    n, block = 12, 4
    indices = _sample_block(random.Random(3), n, n, block)
    assert len(indices) == n
    for start in range(0, n, block):
        run = indices[start:start + block]
        for a, b in zip(run, run[1:]):
            assert b == (a + 1) % n


def test_block_larger_than_series_is_a_rotation() -> None:
    import random

    n = 6
    indices = _sample_block(random.Random(11), n, n, block=n)
    start = indices[0]
    assert indices == [(start + i) % n for i in range(n)]


# ---------------------------------------------------------------- drawdown
def test_exceedance_is_monotone_in_the_threshold() -> None:
    summary = simulate(TRADES, spec(simulations=400))
    keys = ["0.05", "0.10", "0.20"]
    values = [summary.exceedance[k] for k in keys]
    assert values == sorted(values, reverse=True)


def test_drawdown_percentiles_are_ordered() -> None:
    s = simulate(TRADES, spec(simulations=400))
    assert s.p50_max_drawdown <= s.p90_max_drawdown <= s.p95_max_drawdown <= s.p99_max_drawdown


# ---------------------------------------------------------------- ruin
def test_ruin_is_zero_for_a_winning_series_at_small_risk() -> None:
    s = simulate([D("0.5")] * 40, spec(risk_fraction=D("0.001"), simulations=100))
    assert s.ruin_frequency == 0


def test_ruin_is_certain_for_a_losing_series_at_high_risk() -> None:
    s = simulate([D("-1")] * 40, spec(risk_fraction=D("0.5"), ruin_fraction=D("0.5"), simulations=50))
    assert s.ruin_frequency == 1


# ---------------------------------------------------------------- costs
def test_cost_stress_never_reduces_drawdown() -> None:
    base = simulate(TRADES, spec(cost_r=D("0.02"), cost_multiplier=D("1"), simulations=500))
    stressed = simulate(TRADES, spec(cost_r=D("0.02"), cost_multiplier=D("3"), simulations=500))
    assert stressed.mean_max_drawdown >= base.mean_max_drawdown
    assert stressed.ruin_frequency >= base.ruin_frequency


# ---------------------------------------------------------------- sizing
def test_dynamic_sizing_compounds_current_equity() -> None:
    # every trade wins 1R at 1 % of *current* equity → equity multiplies by 1.01 each step
    n = 50
    summary = simulate([D("1")] * n, spec(risk_fraction=D("0.01"), simulations=1, seed=0))
    expected = D("10000") * (D("1.01") ** n)
    assert abs(summary.mean_final_equity - expected) < D("0.05")


def test_float_inputs_are_refused() -> None:
    with pytest.raises(MonteCarloError, match="must be Decimal"):
        simulate([1.0], spec())  # type: ignore[list-item]


# ---------------------------------------------------------------- validation
@pytest.mark.parametrize(
    "overrides",
    [
        {"simulations": 0},
        {"seed": -1},
        {"mode": "wave"},
        {"block_size": 0},
        {"initial_equity": D("0")},
        {"risk_fraction": D("0")},
        {"risk_fraction": D("1")},
        {"ruin_fraction": D("0")},
        {"cost_r": D("-0.01")},
        {"cost_multiplier": D("0")},
        {"dd_thresholds": (D("1"),)},
    ],
)
def test_invalid_spec_is_refused(overrides: dict) -> None:
    with pytest.raises(MonteCarloError):
        spec(**overrides)


def test_empty_series_is_refused() -> None:
    with pytest.raises(MonteCarloError):
        simulate([], spec())


# ---------------------------------------------------------------- comparison
def test_compare_strategies_is_deterministic_and_keyed() -> None:
    strategies = {"alpha": TRADES, "beta": [D("-1")] * 5 + [D("2")] * 5}
    first = compare_strategies(strategies, spec(simulations=100))
    second = compare_strategies(strategies, spec(simulations=100))
    assert list(first) == ["alpha", "beta"]
    assert {k: v.as_dict() for k, v in first.items()} == {k: v.as_dict() for k, v in second.items()}


def test_sensitivity_grid_shape_and_determinism() -> None:
    deltas = (D("-0.1"), D("0"), D("0.1"))
    rrs = (D("0.75"), D("1"), D("1.25"))
    a = sensitivity(TRADES, spec(simulations=50), win_rate_deltas=deltas, rr_multipliers=rrs)
    b = sensitivity(TRADES, spec(simulations=50), win_rate_deltas=deltas, rr_multipliers=rrs)
    assert len(a) == 9
    assert a == b
    assert {"win_rate", "rr_multiplier", "ruin_frequency"} <= set(a[0])


def test_sensitivity_requires_wins_and_losses() -> None:
    with pytest.raises(MonteCarloError):
        sensitivity([D("1")] * 10, spec())


# ---------------------------------------------------------------- report
def test_canonical_digest_ignores_key_order() -> None:
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})


def test_cli_writes_a_reproducible_report(tmp_path: Path) -> None:
    import importlib.util

    source = tmp_path / "trades.json"
    source.write_text(json.dumps({"strategies": {"s1": ["1.5", "-1", "0.8", "-1"]}}), encoding="utf-8")
    out = tmp_path / "report"

    script = ROOT / "scripts" / "montecarlo.py"
    module_spec = importlib.util.spec_from_file_location("mc_cli", script)
    cli = importlib.util.module_from_spec(module_spec)
    assert module_spec and module_spec.loader
    module_spec.loader.exec_module(cli)

    argv = ["--input", str(source), "--out", str(out), "--sims", "50", "--seed", "3", "--cost-multipliers", "1,2"]
    assert cli.main(argv) == 0
    first = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert cli.main(argv) == 0
    second = json.loads((out / "report.json").read_text(encoding="utf-8"))

    assert first["content_sha256"] == second["content_sha256"]
    assert first["input"]["sha256"] == second["input"]["sha256"]
    assert set(first["results"]) == {"1", "2"}
    assert first["assumptions"]


# ---------------------------------------------------------------- safety
def test_no_trading_surface() -> None:
    forbidden = {"order_send", "order_check", "account_info", "positions_get", "initialize"}
    for path in (ROOT / "src/guardian/domain/risk/montecarlo.py", ROOT / "scripts/montecarlo.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name.split(".")[0] != "MetaTrader5" for a in node.names), path.name
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "MetaTrader5", path.name
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                assert name not in forbidden, (path.name, name)
