"""Model training with purged walk-forward validation (no leakage).

Produces a deterministic artifact bundle under ``models/<name>/``:
- model.joblib        serialized estimator + scaler
- metrics.json        per-fold and aggregate OOS metrics (evidence)
- manifest.json       data hash, params, library versions (reproducibility)

Honesty rules enforced in code:
- train/test folds are separated by an embargo >= label horizon;
- the final "evaluation" window is the last contiguous slice never used
  for fitting or tuning;
- if the model does not beat a majority-class baseline on the evaluation
  window, metrics record ``beats_baseline: false`` — the trainer NEVER
  hides this.
"""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

from xauusd_research.schema import Candle

from .features import FEATURE_NAMES, build_dataset

LABEL_HORIZON = 20
EMBARGO_BARS = LABEL_HORIZON * 3


@dataclass(frozen=True)
class TrainConfig:
    name: str = "regime_rf_v1"
    n_estimators: int = 200
    max_depth: int = 8
    min_samples_leaf: int = 50
    random_state: int = 7
    n_splits: int = 4
    eval_fraction: float = 0.2
    stride: int = 10


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _purged_walk_forward_indices(n: int, n_splits: int, eval_fraction: float):
    """Yield (train_idx, test_idx) pairs with an embargo gap between them."""
    eval_start = int(n * (1.0 - eval_fraction))
    usable = list(range(eval_start))
    fold = len(usable) // n_splits
    for k in range(n_splits):
        test_end = fold * (k + 1)
        test_start = fold * k
        if test_start <= 0 or test_end <= test_start:
            continue
        train_end = test_start - EMBARGO_BARS
        if train_end < fold // 2:
            continue
        train_idx = np.asarray(usable[:train_end])
        test_idx = np.asarray(usable[test_start:test_end])
        yield train_idx, test_idx
    # Final untouched evaluation window.
    yield None, np.asarray(list(range(eval_start, n)))


def _fold_metrics(y_true, y_pred) -> dict:
    return {
        "n": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }


def train_model(candles: Sequence[Candle], csv_path: Path, out_dir: Path,
                config: TrainConfig | None = None) -> dict:
    """Train, purged-walk-forward validate and persist the artifact bundle.
    Returns the metrics dict (also written to disk)."""
    cfg = config or TrainConfig()
    xs, ys = build_dataset(candles, horizon=LABEL_HORIZON, stride=cfg.stride)
    X = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=int)
    if len(X) < 2000:
        raise ValueError(f"insufficient samples for honest training: {len(X)}")

    classes = sorted(set(y.tolist()))
    majority = int(np.bincount(y).max()) / len(y)

    fold_reports = []
    for train_idx, test_idx in _purged_walk_forward_indices(len(X), cfg.n_splits, cfg.eval_fraction):
        X_test, y_test = X[test_idx], y[test_idx]
        if train_idx is None:
            # Evaluation window: fit on ALL earlier data (still embargoed by construction).
            earlier = np.arange(0, test_idx[0] - EMBARGO_BARS)
            if len(earlier) < 500:
                continue
            train_idx = earlier
            kind = "final_eval"
        else:
            kind = "walk_forward"
        scaler = StandardScaler().fit(X[train_idx])
        clf = RandomForestClassifier(
            n_estimators=cfg.n_estimators,
            max_depth=cfg.max_depth,
            min_samples_leaf=cfg.min_samples_leaf,
            class_weight="balanced",
            random_state=cfg.random_state,
            n_jobs=-1,
        ).fit(scaler.transform(X[train_idx]), y[train_idx])
        pred = clf.predict(scaler.transform(X_test))
        report = {"kind": kind}
        report.update(_fold_metrics(y_test, pred))
        report["majority_baseline"] = round(float(max(
            np.bincount(y_test, minlength=2)[0], np.bincount(y_test, minlength=2)[1]) / len(y_test)), 4)
        fold_reports.append(report)

    eval_reports = [r for r in fold_reports if r["kind"] == "final_eval"]
    if not eval_reports:
        raise ValueError("no final evaluation window produced")
    ev = eval_reports[-1]
    beats = ev["accuracy"] > ev["majority_baseline"]

    # Refit final production model on everything (documented, deliberate).
    final_scaler = StandardScaler().fit(X)
    final_clf = RandomForestClassifier(
        n_estimators=cfg.n_estimators,
        max_depth=cfg.max_depth,
        min_samples_leaf=cfg.min_samples_leaf,
        class_weight="balanced",
        random_state=cfg.random_state,
        n_jobs=-1,
    ).fit(final_scaler.transform(X), y)

    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": final_scaler, "clf": final_clf, "feature_names": FEATURE_NAMES},
                out_dir / "model.joblib")

    metrics = {
        "schema": "ml-train-metrics/v1",
        "model": cfg.name,
        "samples": int(len(X)),
        "positive_rate": round(float(np.mean(y == 1)), 4),
        "global_majority_baseline": round(majority, 4),
        "folds": fold_reports,
        "final_eval_accuracy": ev["accuracy"],
        "final_eval_beats_baseline": bool(beats),
        "label_horizon": LABEL_HORIZON,
        "embargo_bars": EMBARGO_BARS,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    manifest = {
        "schema": "ml-manifest/v1",
        "model": cfg.name,
        "config": asdict(cfg),
        "data_file": csv_path.name,
        "data_sha256": _file_sha256(csv_path),
        "candles_loaded": len(candles),
        "python": platform.python_version(),
        "sklearn": __import__("sklearn").__version__,
        "numpy": np.__version__,
        "generated_utc": metrics["generated_utc"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return metrics
