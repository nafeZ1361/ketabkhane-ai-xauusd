"""No-look-ahead property for the research features.

A feature row at bar t must be identical whether or not later bars exist. If this
fails, every metric in scripts/research_edge.py is fiction.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "research_edge.py"
spec = importlib.util.spec_from_file_location("research_edge", SCRIPT)
research_edge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research_edge)


def synthetic(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 2000 + np.cumsum(rng.normal(0, 0.4, n))
    idx = pd.date_range("2026-01-01", periods=n, freq="min")
    frame = pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                          "close": close, "spread": 30.0}, index=idx)
    return frame


def test_truncation_does_not_change_past_features():
    full = synthetic()
    cut = 300

    whole = research_edge.features(full).iloc[:cut]
    prefix = research_edge.features(full.iloc[:cut])

    pd.testing.assert_frame_equal(whole, prefix, check_exact=True)


def test_labels_use_the_future_not_the_present():
    full = synthetic()
    fwd = full["close"].shift(-5) / full["close"] - 1.0

    assert np.isnan(fwd.iloc[-5:]).all()
    assert np.isfinite(fwd.iloc[:-5]).all()
