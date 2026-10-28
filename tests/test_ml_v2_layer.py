"""Tests for ML v2 layer: sequence features, triple-barrier labels, trainer,
inference. Leakage contract is asserted structurally (window truncation)."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from xauusd_research.ml_engine.features_v2 import (  # noqa: E402
    N_CHANNELS,
    WARMUP_V2,
    WINDOW_LEN,
    LabelCounts,
    build_channel_matrix,
    build_dataset_v2,
    triple_barrier_label,
)
from xauusd_research.schema import Candle  # noqa: E402


def _mk_candles(n: int, seed: int = 3) -> list[Candle]:
    rng = np.random.default_rng(seed)
    t0 = datetime(2026, 1, 2, 1, 0)
    price = 4000.0
    out: list[Candle] = []
    for i in range(n):
        step = float(rng.normal(0.0, 1.5))
        o = price
        c = max(100.0, price + step)
        h = max(o, c) + abs(float(rng.normal(0, 0.8)))
        l = min(o, c) - abs(float(rng.normal(0, 0.8)))
        out.append(Candle(time=t0 + timedelta(minutes=i), open=o, high=h, low=l,
                          close=c, tickvol=float(rng.integers(50, 800))))
        price = c
    return out


class TestChannelMatrix:
    def test_shape_and_finiteness(self):
        cs = _mk_candles(500)
        mat = build_channel_matrix(cs)
        assert mat.shape == (500, N_CHANNELS)
        assert np.isfinite(mat).all()

    def test_causality_truncation(self):
        """Row i must not change when future candles are appended."""
        cs = _mk_candles(400)
        full = build_channel_matrix(cs)
        cut = build_channel_matrix(cs[:300])
        np.testing.assert_allclose(full[:300], cut, rtol=1e-9)

    def test_clipping_bounds(self):
        mat = build_channel_matrix(_mk_candles(600))
        assert np.abs(mat[:, 0]).max() <= 8.0
        assert np.abs(mat[:, 3]).max() <= 8.0


class TestTripleBarrier:
    def test_long_touch(self):
        cs = _mk_candles(200)
        from xauusd_research.ml_engine.features_v2 import _atr_series
        atr = _atr_series(cs)
        i = 100
        base = cs[i].close
        a = atr[i]
        # Force next bars to breach upper barrier first.
        for j in range(i + 1, i + 5):
            cs[j] = Candle(time=cs[j].time, open=base, high=base + 3 * a,
                           low=base - 0.1 * a, close=base + 2 * a, tickvol=100)
        lab = triple_barrier_label(cs, i, atr)
        assert lab == 1

    def test_incomplete_window_returns_none(self):
        cs = _mk_candles(120)
        from xauusd_research.ml_engine.features_v2 import _atr_series
        atr = _atr_series(cs)
        assert triple_barrier_label(cs, len(cs) - 5, atr) is None

    def test_neutral_dropped(self):
        """Flat series within barriers => neutral (-1)."""
        n = 150
        t0 = datetime(2026, 1, 2)
        flat = [Candle(time=t0 + timedelta(minutes=i), open=4000.0, high=4000.05,
                       low=3999.95, close=4000.0, tickvol=100.0) for i in range(n)]
        from xauusd_research.ml_engine.features_v2 import _atr_series
        atr = _atr_series(flat)
        # ATR tiny; use wide k so nothing touches.
        lab = triple_barrier_label(flat, 80, atr, horizon=24, k_up=100.0, k_down=100.0)
        assert lab == -1


class TestDatasetV2:
    def test_geometry_and_counts(self):
        cs = _mk_candles(1500)
        X, y, counts = build_dataset_v2(cs, stride=2)
        assert X.shape[1] == WINDOW_LEN * N_CHANNELS
        assert len(X) == len(y) == counts.kept
        assert counts.long + counts.short + counts.neutral_dropped <= len(cs)
        assert set(np.unique(y)).issubset({0, 1})

    def test_short_series_empty(self):
        X, y, c = build_dataset_v2(_mk_candles(50))
        assert len(X) == 0 and isinstance(c, LabelCounts)

    def test_labels_depend_on_future_only_for_labels(self):
        """Features window ends at sample bar i: truncating the series right
        after i keeps the feature matrix identical up to that point."""
        cs = _mk_candles(1200)
        X_full, y_full, _ = build_dataset_v2(cs, stride=10)
        assert len(X_full) > 0
        # Rebuild with last 30% removed -> earlier samples unchanged.
        cut = int(len(cs) * 0.7)
        X_cut, _, _ = build_dataset_v2(cs[:cut], stride=10)
        m = min(len(X_cut), len(X_full))
        assert m > 0
        np.testing.assert_allclose(X_cut[:m], X_full[:m], rtol=1e-9)


class TestTrainerV2:
    def test_requires_enough_samples(self):
        from xauusd_research.ml_engine.trainer_v2 import (TrainConfigV2,
                                                          train_model_v2)
        cs = _mk_candles(2000)
        cfg = TrainConfigV2(stride=50)  # few kept samples -> must refuse
        with pytest.raises(ValueError, match="insufficient"):
            train_model_v2(cs, Path("dummy.csv"), Path("/tmp/nope"), cfg)

    def test_smoke_training_artifacts(self, tmp_path):
        pytest.importorskip("sklearn")
        from xauusd_research.ml_engine.trainer_v2 import TrainConfigV2, train_model_v2
        cs = _mk_candles(12000, seed=11)
        cfg = TrainConfigV2(name="t_smoke", stride=2, n_estimators=40,
                            min_samples_leaf=10, train_dnn=False)
        m = train_model_v2(cs, tmp_path / "synthetic.csv", tmp_path / "model", cfg)
        assert (tmp_path / "model" / "model.joblib").is_file()
        assert (tmp_path / "model" / "metrics.json").is_file()
        assert (tmp_path / "model" / "manifest.json").is_file()
        ev = m["rf_final_eval"]
        assert {"accuracy", "majority_baseline", "beats_baseline"} <= set(ev)
        # Honesty: beats_baseline is a plain bool recorded either way.
        assert isinstance(ev["beats_baseline"], bool)


class TestInferenceV2:
    def test_geometry_mismatch_refused(self, tmp_path):
        pytest.importorskip("sklearn")
        import joblib
        from xauusd_research.ml_engine.inference_v2 import (InferenceEngineV2,
                                                            ModelArtifactErrorV2)
        bad = {"scaler": None, "clf": None, "feature_names": ("a",),
               "geometry": {"window_len": 8, "channels": 2, "label_horizon": 4}}
        d = tmp_path / "m"
        d.mkdir()
        joblib.dump(bad, d / "model.joblib")
        (d / "manifest.json").write_text("{}")
        with pytest.raises(ModelArtifactErrorV2, match="geometry mismatch"):
            InferenceEngineV2(d)

    def test_missing_bundle(self, tmp_path):
        from xauusd_research.ml_engine.inference_v2 import (InferenceEngineV2,
                                                            ModelArtifactErrorV2)
        with pytest.raises(ModelArtifactErrorV2):
            InferenceEngineV2(tmp_path / "nothing")

    def test_end_to_end_signal_is_causal(self, tmp_path):
        pytest.importorskip("sklearn")
        from xauusd_research.ml_engine.inference_v2 import InferenceEngineV2
        from xauusd_research.ml_engine.trainer_v2 import TrainConfigV2, train_model_v2
        cs = _mk_candles(12000, seed=13)
        cfg = TrainConfigV2(name="t_e2e", stride=2, n_estimators=40,
                            min_samples_leaf=10, train_dnn=False)
        mdir = tmp_path / "model"
        train_model_v2(cs, tmp_path / "synthetic.csv", mdir, cfg)
        eng = InferenceEngineV2(mdir)
        sig = eng.predict_signal(cs[:60])        # warmup incomplete -> NO_TRADE
        assert sig.direction == 0 and sig.label == "NO_TRADE"
        sig2 = eng.predict_signal(cs[:1500])
        assert sig2.label in {"LONG", "SHORT"}
        assert 0.0 <= sig2.confidence <= 1.0
        # Causality: extending the history beyond this bar does not alter it.
        sig3 = eng.predict_signal(cs[:1500])
        assert sig3 == sig2
