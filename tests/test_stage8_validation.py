"""Tests for Stage 8 validation tools (GAP-005 Monte Carlo, GAP-006/007 landscape).

Unit tests run on synthetic fixtures only; the frozen-evidence integration checks
are skipped automatically when stage7/evidence/run1 is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stage8.monte_carlo import (MonteCarloError, _drawdown_stats, load_trade_pnls,
                                run_monte_carlo, verify_frozen_inputs)
from stage8.landscape import (BASELINE_COST, COST_GRID_USD, THRESHOLD_GRID,
                              LandscapeError)

REPO = Path(__file__).resolve().parents[1]
RUN1 = REPO / "stage7" / "evidence" / "run1"
frozen_required = pytest.mark.skipif(
    not (RUN1 / "trades.csv").is_file(), reason="frozen run1 evidence not present")


# --------------------------------------------------------------------- units
def test_drawdown_stats_known_sequence():
    pnls = np.array([100.0, -250.0, 50.0, -30.0])
    usd, pct = _drawdown_stats(pnls, initial_equity=1000.0)
    # equity: 1100, 850, 900, 870 -> peak 1100, worst trough 850 => dd -250
    assert usd == pytest.approx(-250.0)
    assert pct == pytest.approx(-250.0 / 1100.0 * 100.0)


def test_monte_carlo_determinism_and_shapes():
    rng = np.random.default_rng(7)
    pnls = rng.normal(-1.0, 10.0, size=500)
    a = run_monte_carlo(pnls, replicates=50, base_seed=42, initial_equity=100_000.0)
    b = run_monte_carlo(pnls, replicates=50, base_seed=42, initial_equity=100_000.0)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["replicates"] == 50 and a["trades_per_replicate"] == 500
    tail = a["tail_probabilities"]
    for v in tail.values():
        assert 0.0 <= v <= 1.0
    dist = a["distribution_max_drawdown_usd"]
    assert dist["min"] <= dist["p5"] <= dist["median"] <= dist["p95"] <= dist["max"] <= 0.0


def test_negative_expectancy_never_positive_in_mc_mean():
    pnls = np.full(200, -5.0)
    s = run_monte_carlo(pnls, replicates=20, base_seed=1, initial_equity=1000.0)
    assert s["distribution_final_pnl"]["mean"] == pytest.approx(-1000.0)
    assert s["tail_probabilities"]["p_final_pnl_positive"] == 0.0


def test_grid_constants_pre_registered():
    assert BASELINE_COST == 0.30  # baseline cost pinned to run1 contract
    assert COST_GRID_USD == (0.00, 0.20, 0.30, 0.50)
    assert THRESHOLD_GRID == (0.50, 0.55, 0.60)


# ---------------------------------------------------------- frozen evidence
@frozen_required
def test_verify_frozen_inputs_passes_on_untouched_run1():
    verified = verify_frozen_inputs(RUN1)
    manifest = json.loads((RUN1 / "run_manifest.json").read_text())
    for name, digest in verified.items():
        expected = manifest["artifact_hashes_sha256"].get(name)
        if expected is not None:
            assert digest == expected


@frozen_required
def test_verify_frozen_inputs_detects_tampering(tmp_path):
    import shutil
    for f in ("trades.csv", "performance_metrics.json", "predictions.csv",
              "equity_curve.csv", "run_manifest.json"):
        shutil.copy(RUN1 / f, tmp_path / f)
    (tmp_path / "trades.csv").write_text("pnl\n1.0\n")
    with pytest.raises(MonteCarloError, match="integrity violation"):
        verify_frozen_inputs(tmp_path)


@frozen_required
def test_load_trade_pnls_matches_metrics(tmp_path=None):
    pnls = load_trade_pnls(RUN1)
    metrics = json.loads((RUN1 / "performance_metrics.json").read_text())
    assert len(pnls) == metrics["trades"]
    assert round(float(pnls.sum()), 6) == metrics["net_pnl"]


@frozen_required
def test_refuses_write_into_frozen_dirs(tmp_path, monkeypatch):
    from stage8 import monte_carlo as mc
    monkeypatch.chdir(REPO)
    with pytest.raises(MonteCarloError, match="frozen"):
        mc.main(["stage7/evidence/run1"])
