"""Tests for the ML training/inference layer (features, trainer, inference).

All tests run on small synthetic series — no dependency on the repo CSV.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from xauusd_research.ml_engine.features import (
    FEATURE_NAMES,
    WARMUP,
    build_dataset,
    compute_features,
    make_labels,
)
from xauusd_research.schema import Candle


def _series(n: int, drift: float = 0.0001, noise: float = 0.0005) -> list[Candle]:
    candles = []
    price = 4000.0
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    for i in range(n):
        price *= 1.0 + drift + noise * math.sin(i / 3.0)
        o = price
        h = price * 1.0004
        l = price * 0.9996
        c = price * (1.0 + drift)
        candles.append(Candle(
            time=datetime.fromtimestamp(t0.timestamp() + i * 60, tz=timezone.utc),
            open=o, high=h, low=l, close=c, tickvol=float(100 + (i % 7) * 10)))
    return candles


class TestFeatures:
    def test_warmup_returns_none(self):
        candles = _series(100)
        assert compute_features(candles, WARMUP - 1) is None
        assert compute_features(candles, WARMUP) is not None

    def test_feature_count_and_finiteness(self):
        feats = compute_features(_series(300), 299)
        assert feats is not None and len(feats) == len(FEATURE_NAMES)
        assert all(math.isfinite(f) for f in feats)

    def test_non_repainting_prefix_stability(self):
        """Feature vector at bar i must be identical whether computed on the
        full series or a truncated prefix ending at i."""
        candles = _series(400)
        full = compute_features(candles, 399)
        prefix = compute_features(candles[:400], 399)
        assert full == prefix
        # And a longer series does not change earlier bars' features.
        longer = _series(450)
        # first 400 bars of both series are identical by construction
        assert compute_features(longer, 399) == full

    def test_labels_directions(self):
        up = _series(200, drift=0.0005)
        down = _series(200, drift=-0.0005)
        assert make_labels(up, 100, horizon=20, threshold=0.0001) == 1
        assert make_labels(down, 100, horizon=20, threshold=0.0001) == 0
        flat = _series(200, drift=0.0, noise=0.0)
        assert make_labels(flat, 100, horizon=20, threshold=0.001) == -1
        assert make_labels(_series(50), 45, horizon=20) is None

    def test_build_dataset_drops_neutral(self):
        xs, ys = build_dataset(_series(1000, drift=0.0005), horizon=20,
                               threshold=0.0001, stride=1)
        assert len(xs) == len(ys) > 0
        assert set(ys) <= {0, 1}
        assert all(len(x) == len(FEATURE_NAMES) for x in xs)


class TestInferenceAndReconciliation:
    def test_missing_artifact_raises(self, tmp_path):
        from xauusd_research.ml_engine.inference import InferenceEngine, ModelArtifactError
        with pytest.raises(ModelArtifactError):
            InferenceEngine(tmp_path)

    def test_reconciliation_rules(self):
        from xauusd_research.ml_engine.inference import Signal, reconcile_with_regime_tree
        from xauusd_research.ml_engine.regime_tree import (
            MarketRegime, RegimeClassification, RegimeFeatures)

        feats = RegimeFeatures(1.0, 0.0, 1.0, 0.0)

        def clf(regime, gate):
            return RegimeClassification(regime, 0.7, 1.0, gate, feats)

        sig_long = Signal(1, "LONG", 0.8, (), "t")
        assert reconcile_with_regime_tree(sig_long, clf(MarketRegime.BULL_TREND, "ALLOW_TREND"))["verdict"] == "AGREE"
        assert reconcile_with_regime_tree(sig_long, clf(MarketRegime.VOLATILITY_SHOCK, "CASH_LOCKOUT"))["verdict"] == "VETOED_BY_RISK_GATE"
        assert reconcile_with_regime_tree(sig_long, clf(MarketRegime.CHOPPY_RANGE, "ALLOW_RANGE"))["verdict"] == "TREE_NO_DIRECTION"
        weak = Signal(1, "LONG", 0.4, (), "t")
        assert reconcile_with_regime_tree(weak, clf(MarketRegime.BULL_TREND, "ALLOW_TREND"))["verdict"] == "DISAGREE"
        bearish = Signal(-1, "SHORT", 0.9, (), "t")
        assert reconcile_with_regime_tree(bearish, clf(MarketRegime.BULL_TREND, "ALLOW_TREND"))["verdict"] == "DISAGREE"

    def test_end_to_end_train_predict(self, tmp_path):
        """Full bundle lifecycle on synthetic data with tiny thresholds."""
        from xauusd_research.ml_engine.inference import InferenceEngine
        from xauusd_research.ml_engine.trainer import TrainConfig, train_model

        # Alternating regimes so a tree can learn something deterministic.
        candles = _series(1500, drift=0.0008) + _series(1500, drift=-0.0008) \
            + _series(1500, drift=0.0008) + _series(1500, drift=-0.0008)
        csv = tmp_path / "synthetic.csv"
        csv.write_text("placeholder", encoding="utf-8")  # only hashed for manifest
        cfg = TrainConfig(name="unit_test_rf", n_estimators=20, max_depth=4,
                          min_samples_leaf=10, n_splits=2, eval_fraction=0.25,
                          stride=1)
        metrics = train_model(candles, csv, tmp_path / "model", cfg)
        assert metrics["schema"] == "ml-train-metrics/v1"
        assert (tmp_path / "model" / "model.joblib").is_file()
        assert (tmp_path / "model" / "metrics.json").is_file()
        assert (tmp_path / "model" / "manifest.json").is_file()
        loaded = json.loads((tmp_path / "model" / "metrics.json").read_text(encoding="utf-8"))
        assert loaded["samples"] == metrics["samples"]

        eng = InferenceEngine(tmp_path / "model")
        sig = eng.predict_signal(candles[-300:])
        assert sig.direction in (-1, 1)
        assert 0.0 < sig.confidence <= 1.0
        series = eng.predict_series(candles[-300:], stride=50)
        assert len(series) >= 3
        assert all(s.direction in (-1, 1) for s in series)

    def test_insufficient_samples_guard(self, tmp_path):
        from xauusd_research.ml_engine.trainer import TrainConfig, train_model
        csv = tmp_path / "tiny.csv"
        csv.write_text("x", encoding="utf-8")
        with pytest.raises(ValueError, match="insufficient samples"):
            train_model(_series(300), csv, tmp_path / "m", TrainConfig(stride=1))
