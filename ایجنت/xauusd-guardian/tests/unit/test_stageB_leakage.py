"""Stage B: D1 (purge) and D2 (timestamp horizon) negative tests.

These are written to fail against the pre-Stage-B harness: it had no forward_label()
and no purged_split(), and it measured the horizon in rows.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "research_edge.py"
spec = importlib.util.spec_from_file_location("research_edge", SCRIPT)
research_edge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research_edge)


def frame(times: list[pd.Timestamp]) -> pd.DataFrame:
    close = 2000.0 + np.arange(len(times), dtype=float)
    return pd.DataFrame(
        {"open": close, "high": close + 0.5, "low": close - 0.5,
         "close": close, "spread": 30.0},
        index=pd.DatetimeIndex(times),
    )


def test_D2_label_time_is_first_bar_at_or_after_horizon():
    base = pd.Timestamp("2026-01-05 00:00")
    # a 100-minute hole after the third bar
    times = [base, base + pd.Timedelta(minutes=1), base + pd.Timedelta(minutes=2),
             base + pd.Timedelta(minutes=102), base + pd.Timedelta(minutes=103)]
    df = frame(times)

    fwd, label_time = research_edge.forward_label(df, 15)

    # target for bar 0 is 00:15; the first bar at/after it is 01:42 (row 3)
    assert label_time.iloc[0] == times[3]
    assert label_time.iloc[0] - df.index[0] >= pd.Timedelta(minutes=15)
    assert fwd.iloc[0] == pytest.approx(df["close"].iloc[3] / df["close"].iloc[0] - 1.0)


def test_D2_rows_without_a_future_bar_are_invalid():
    base = pd.Timestamp("2026-01-05 00:00")
    times = [base + pd.Timedelta(minutes=i) for i in range(20)]
    df = frame(times)

    fwd, label_time = research_edge.forward_label(df, 15)

    assert pd.isna(label_time.iloc[-1])
    assert pd.isna(fwd.iloc[-1])
    assert not pd.isna(label_time.iloc[0])  # 00:15 exists


def test_D1_purge_drops_training_labels_crossing_the_boundary():
    base = pd.Timestamp("2026-01-05 00:00")
    times = [base + pd.Timedelta(minutes=i) for i in range(100)]
    df = frame(times)

    fwd, label_time = research_edge.forward_label(df, 15)
    train_mask, test_mask, stats = research_edge.purged_split(df, label_time, 15)

    test_start = df.index[int(len(df) * 0.7)]
    leaked = label_time[train_mask] >= test_start
    assert not leaked.any(), "a training label still reaches into the test period"
    assert train_mask.sum() + stats["train_dropped_boundary"] + stats["train_dropped_embargo"] \
        + stats["invalid"] <= int(len(df) * 0.7)
    assert test_mask.sum() == len(df) - int(len(df) * 0.7)


def test_D1_embargo_is_one_horizon():
    base = pd.Timestamp("2026-01-05 00:00")
    times = [base + pd.Timedelta(minutes=i) for i in range(100)]
    df = frame(times)
    fwd, label_time = research_edge.forward_label(df, 15)

    train_mask, _, stats = research_edge.purged_split(df, label_time, 15)

    test_start = df.index[int(len(df) * 0.7)]
    embargo = pd.Timedelta(minutes=15)
    kept = label_time[train_mask]
    assert (kept < test_start - embargo).all()
    assert stats["embargo"] == "1x horizon"
