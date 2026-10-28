"""Inference entry point for the trained regime model.

Loads a persisted artifact bundle (model.joblib + manifest.json), verifies
the training-data hash is recorded, and produces signal decisions from a
candle series. This module performs NO fitting and NEVER peeks beyond the
last candle it is given (non-repainting by construction).

Integration contract with the existing hand-written engine:
- ``predict_signal`` returns an ML-side opinion (direction/confidence);
- ``reconcile_with_regime_tree`` compares it against
  ``RegimeDecisionEngine`` output so the feedback loop can log agreement /
  disagreement instead of silently overriding either source.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np

from xauusd_research.schema import Candle

from .features import FEATURE_NAMES, compute_features
from .regime_tree import MarketRegime, RegimeClassification, RegimeDecisionEngine


class ModelArtifactError(RuntimeError):
    """Raised when the on-disk model bundle is missing or inconsistent."""


@dataclass(frozen=True)
class Signal:
    direction: int            # 1 = LONG, -1 = SHORT, 0 = NO_TRADE
    label: str                # "LONG" | "SHORT" | "NO_TRADE"
    confidence: float         # max class probability, 0..1
    features: tuple[float, ...]
    bar_time: str


class InferenceEngine:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        bundle_path = self.model_dir / "model.joblib"
        manifest_path = self.model_dir / "manifest.json"
        if not bundle_path.is_file():
            raise ModelArtifactError(f"missing model artifact: {bundle_path}")
        if not manifest_path.is_file():
            raise ModelArtifactError(f"missing manifest: {manifest_path}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bundle = joblib.load(bundle_path)
        try:
            self.scaler = bundle["scaler"]
            self.clf = bundle["clf"]
        except KeyError as exc:  # pragma: no cover - corrupted artifact
            raise ModelArtifactError(f"artifact bundle missing key: {exc}") from exc
        stored_names = tuple(bundle.get("feature_names", ()))
        if stored_names and stored_names != FEATURE_NAMES:
            raise ModelArtifactError(
                "feature-name mismatch between artifact and code; retrain required")

    @property
    def classes(self) -> list[int]:
        return [int(c) for c in self.clf.classes_]

    def predict_signal(self, candles: Sequence[Candle]) -> Signal:
        """Emit a signal for the LAST candle of ``candles`` using history only."""
        idx = len(candles) - 1
        feats = compute_features(candles, idx)
        if feats is None:
            return Signal(0, "NO_TRADE", 0.0, (), candles[idx].time.isoformat())
        X = self.scaler.transform(np.asarray([feats], dtype=float))
        proba = self.clf.predict_proba(X)[0]
        pred_class = int(self.clf.predict(X)[0])
        conf = float(proba[list(self.classes).index(pred_class)])
        if pred_class == 1:
            direction, label = 1, "LONG"
        elif pred_class == 0:
            direction, label = -1, "SHORT"
        else:  # pragma: no cover - labels are binary by construction
            direction, label = 0, "NO_TRADE"
        return Signal(direction, label, round(conf, 4), feats,
                      candles[idx].time.isoformat())

    def predict_series(self, candles: Sequence[Candle], stride: int = 1) -> list[Signal]:
        out: list[Signal] = []
        for i in range(len(candles)):
            if i % max(1, stride):
                continue
            feats = compute_features(candles, i)
            if feats is None:
                continue
            X = self.scaler.transform(np.asarray([feats], dtype=float))
            proba = self.clf.predict_proba(X)[0]
            pred_class = int(self.clf.predict(X)[0])
            conf = float(proba[list(self.classes).index(pred_class)])
            direction = {1: 1, 0: -1}.get(pred_class, 0)
            label = {1: "LONG", 0: "SHORT"}.get(pred_class, "NO_TRADE")
            out.append(Signal(direction, label, round(conf, 4), feats,
                              candles[i].time.isoformat()))
        return out


def reconcile_with_regime_tree(signal: Signal,
                              regime: RegimeClassification) -> dict:
    """Structured agreement record consumed by the feedback loop / audit.

    Rules (conservative, hard-coded — no silent override):
    - VOLATILITY_SHOCK gate always vetoes any ML direction (risk first);
    - agreement requires same sign AND ML confidence >= 0.55;
    - everything else is "DISAGREE" and must be logged, not traded.
    """
    tree_direction = {
        MarketRegime.BULL_TREND: 1,
        MarketRegime.BEAR_TREND: -1,
    }.get(regime.regime, 0)
    vetoed = regime.action_gate == "CASH_LOCKOUT"
    if vetoed:
        verdict = "VETOED_BY_RISK_GATE"
    elif signal.direction == 0:
        verdict = "ML_NO_OPINION"
    elif tree_direction == 0:
        verdict = "TREE_NO_DIRECTION"
    elif tree_direction == signal.direction and signal.confidence >= 0.55:
        verdict = "AGREE"
    else:
        verdict = "DISAGREE"
    return {
        "schema": "ml-tree-reconciliation/v1",
        "bar_time": signal.bar_time,
        "ml": {"direction": signal.direction, "label": signal.label,
               "confidence": signal.confidence},
        "tree": {"regime": regime.regime.value, "confidence": regime.confidence,
                 "action_gate": regime.action_gate},
        "verdict": verdict,
        "trade_allowed": verdict == "AGREE",
    }
