"""Inference engine v2 — loads the sequence-geometry artifact bundle.

Mirrors the v1 contract: NO fitting, strictly causal (uses candles up to the
requested bar only), refuses artifacts whose geometry does not match code.
Optional DNN head is loaded when ``dnn.pt`` + ``dnn_scaler.joblib`` exist and
torch is importable; otherwise RF-only inference proceeds with a note.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np

from xauusd_research.schema import Candle

from .features_v2 import (
    CHANNEL_NAMES,
    LABEL_HORIZON_V2,
    N_CHANNELS,
    WARMUP_V2,
    WINDOW_LEN,
    build_channel_matrix,
)


class ModelArtifactErrorV2(RuntimeError):
    """Raised when the on-disk v2 bundle is missing or inconsistent."""


@dataclass(frozen=True)
class SignalV2:
    direction: int          # 1 LONG / -1 SHORT / 0 NO_TRADE
    label: str
    confidence: float       # max softmax probability
    source: str             # "rf" | "ensemble"
    bar_time: str


EXPECTED_GEOMETRY = {
    "window_len": WINDOW_LEN,
    "channels": N_CHANNELS,
    "label_horizon": LABEL_HORIZON_V2,
}


class InferenceEngineV2:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = Path(model_dir)
        bundle_path = self.model_dir / "model.joblib"
        manifest_path = self.model_dir / "manifest.json"
        if not bundle_path.is_file():
            raise ModelArtifactErrorV2(f"missing model artifact: {bundle_path}")
        if not manifest_path.is_file():
            raise ModelArtifactErrorV2(f"missing manifest: {manifest_path}")
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        bundle = joblib.load(bundle_path)
        try:
            self.scaler = bundle["scaler"]
            self.clf = bundle["clf"]
        except KeyError as exc:
            raise ModelArtifactErrorV2(f"artifact bundle missing key: {exc}") from exc
        geom = bundle.get("geometry", {})
        for k, v in EXPECTED_GEOMETRY.items():
            if geom.get(k) != v:
                raise ModelArtifactErrorV2(
                    f"geometry mismatch on '{k}': artifact={geom.get(k)} code={v}; "
                    "retrain required")
        names = tuple(bundle.get("feature_names", ()))
        if names and names != CHANNEL_NAMES:
            raise ModelArtifactErrorV2("channel-name mismatch; retrain required")
        self._dnn = self._maybe_load_dnn()

    def _maybe_load_dnn(self):
        pt = self.model_dir / "dnn.pt"
        sc = self.model_dir / "dnn_scaler.joblib"
        if not (pt.is_file() and sc.is_file()):
            return None
        try:
            import torch
            from .trainer_v2 import _build_dnn
            ck = torch.load(pt, map_location="cpu", weights_only=True)
            model = _build_dnn(torch, ck["in_dim"], ck["hidden"])
            model.load_state_dict(ck["state_dict"])
            model.eval()
            scaler = joblib.load(sc)
            return (model, scaler)
        except Exception:
            return None   # degrade to RF-only, never crash inference

    @property
    def classes(self) -> list[int]:
        return [int(c) for c in self.clf.classes_]

    def predict_signal(self, candles: Sequence[Candle]) -> SignalV2:
        idx = len(candles) - 1
        if idx < WARMUP_V2 + WINDOW_LEN - 1:
            return SignalV2(0, "NO_TRADE", 0.0, "rf", candles[idx].time.isoformat())
        mat = build_channel_matrix(candles)
        win = mat[idx - WINDOW_LEN + 1: idx + 1].reshape(1, -1)
        Xs = self.scaler.transform(win)
        proba = self.clf.predict_proba(Xs)[0]
        pred_class = int(self.clf.predict(Xs)[0])
        conf = float(proba[list(self.classes).index(pred_class)])
        source = "rf"
        if self._dnn is not None:
            import torch
            model, dscaler = self._dnn
            with torch.no_grad():
                logits = model(torch.tensor(dscaler.transform(win), dtype=torch.float32))
                dp = torch.softmax(logits, dim=1).numpy()[0]
                dcls = int(np.argmax(dp))
                dconf = float(dp[dcls])
            # Ensemble: average probabilities of both heads.
            rf_p = {c: float(proba[i]) for i, c in enumerate(self.classes)}
            avg = (rf_p.get(dcls, 0.0) + dconf) / 2.0 if dcls == pred_class else \
                  max(rf_p.get(dcls, 0.0), dconf) * 0.5
            if dcls != pred_class and dconf > conf:
                pred_class, conf = dcls, avg
            elif dcls == pred_class:
                conf = min(1.0, (conf + dconf) / 2.0)
            source = "ensemble"
        direction = {1: 1, 0: -1}.get(pred_class, 0)
        label = {1: "LONG", 0: "SHORT"}.get(pred_class, "NO_TRADE")
        return SignalV2(direction, label, round(conf, 4), source,
                        candles[idx].time.isoformat())
