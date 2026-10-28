"""Trainer v2 — purged walk-forward over sequence features, RF + DNN.

Same honesty contract as trainer v1, extended:
- embargo >= label horizon between any train slice and its test slice;
- final evaluation window is never used for fitting or tuning;
- ``beats_baseline`` recorded per model kind; the trainer NEVER hides it;
- DNN (PyTorch) is only trained when torch is importable; otherwise the
  experiment degrades to RF-only with an explicit note in metrics.

DNN early-stopping uses a *tail slice of the training data* (never the test
window), preserving the purged protocol.
"""
from __future__ import annotations

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

from .features_v2 import (
    CHANNEL_NAMES,
    LABEL_HORIZON_V2,
    N_CHANNELS,
    WINDOW_LEN,
    build_dataset_v2,
)

EMBARGO_BARS_V2 = LABEL_HORIZON_V2 * 3


@dataclass(frozen=True)
class TrainConfigV2:
    name: str = "regime_v2"
    n_estimators: int = 300
    max_depth: int = 10
    min_samples_leaf: int = 40
    random_state: int = 7
    n_splits: int = 4
    eval_fraction: float = 0.2
    stride: int = 5
    k_up: float = 1.0
    k_down: float = 1.0
    # DNN
    dnn_hidden: int = 64
    dnn_epochs: int = 30
    dnn_lr: float = 1e-3
    dnn_batch: int = 256
    dnn_patience: int = 6
    train_dnn: bool = True


def _file_sha256(path: Path) -> str:
    """Hash the training file when it exists; otherwise hash a canonical
    description of the in-memory dataset (tests/synthetic runs must still
    produce a reproducible evidence field)."""
    if path.is_file():
        h = __import__("hashlib").sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    h = __import__("hashlib").sha256()
    h.update(f"virtual:{path.name}".encode("utf-8"))
    return h.hexdigest()


def _purged_walk_forward_indices(n: int, n_splits: int, eval_fraction: float):
    eval_start = int(n * (1.0 - eval_fraction))
    usable = list(range(eval_start))
    fold = len(usable) // n_splits
    for k in range(n_splits):
        test_end = fold * (k + 1)
        test_start = fold * k
        if test_start <= 0 or test_end <= test_start:
            continue
        train_end = test_start - EMBARGO_BARS_V2
        if train_end < fold // 2:
            continue
        yield np.asarray(usable[:train_end]), np.asarray(usable[test_start:test_end])
    yield None, np.asarray(list(range(eval_start, n)))


def _fold_metrics(y_true, y_pred, majority_base) -> dict:
    return {
        "n": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "majority_baseline": round(float(majority_base), 4),
        "beats_baseline": bool(accuracy_score(y_true, y_pred) > majority_base),
    }


def _baseline_rate(y_test: np.ndarray) -> float:
    counts = np.bincount(y_test, minlength=2)
    return float(max(counts[0], counts[1]) / len(y_test)) if len(y_test) else 0.5


# ---------------------------------------------------------------------------
# DNN (PyTorch, optional)
# ---------------------------------------------------------------------------

def _torch_available():
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def _build_dnn(torch, in_dim: int, hidden: int):
    class RegimeNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.net = torch.nn.Sequential(
                torch.nn.Linear(in_dim, hidden),
                torch.nn.ReLU(),
                torch.nn.Dropout(0.3),
                torch.nn.Linear(hidden, hidden // 2),
                torch.nn.ReLU(),
                torch.nn.Dropout(0.2),
                torch.nn.Linear(hidden // 2, 2),
            )

        def forward(self, x):
            return self.net(x)

    return RegimeNet()


def _train_dnn(X_tr, y_tr, X_val, y_val, cfg: TrainConfigV2):
    """Return (model, scaler, val_accuracy) or None when torch missing."""
    if not _torch_available():
        return None
    import torch

    torch.manual_seed(cfg.random_state)
    np.random.seed(cfg.random_state)
    scaler = StandardScaler().fit(X_tr)
    Xt = torch.tensor(scaler.transform(X_tr), dtype=torch.float32)
    yt = torch.tensor(y_tr, dtype=torch.long)
    Xv = torch.tensor(scaler.transform(X_val), dtype=torch.float32)
    yv = torch.tensor(y_val, dtype=torch.long)

    model = _build_dnn(torch, X_tr.shape[1], cfg.dnn_hidden)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.dnn_lr, weight_decay=1e-4)
    lossf = torch.nn.CrossEntropyLoss()
    best_val, best_state, bad = float("inf"), None, 0
    ds = torch.utils.data.TensorDataset(Xt, yt)
    dl = torch.utils.data.DataLoader(ds, batch_size=cfg.dnn_batch, shuffle=True)
    for _epoch in range(cfg.dnn_epochs):
        model.train()
        for xb, yb in dl:
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            vloss = float(lossf(model(Xv), yv))
        if vloss < best_val - 1e-4:
            best_val, bad = vloss, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.dnn_patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        acc = float((model(Xv).argmax(1) == yv).float().mean())
    return model, scaler, acc


def _dnn_predict(model, scaler, X: np.ndarray) -> np.ndarray:
    import torch
    with torch.no_grad():
        t = torch.tensor(scaler.transform(X), dtype=torch.float32)
        return model(t).argmax(1).numpy()


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def train_model_v2(candles: Sequence[Candle], csv_path: Path, out_dir: Path,
                   config: TrainConfigV2 | None = None) -> dict:
    cfg = config or TrainConfigV2()
    X, y, counts = build_dataset_v2(candles, k_up=cfg.k_up, k_down=cfg.k_down,
                                    stride=cfg.stride)
    if len(X) < 3000:
        raise ValueError(f"insufficient samples for honest training: {len(X)}")

    fold_reports: list[dict] = []
    dnn_fold_reports: list[dict] = []
    have_torch = _torch_available()

    for train_idx, test_idx in _purged_walk_forward_indices(len(X), cfg.n_splits,
                                                            cfg.eval_fraction):
        X_test, y_test = X[test_idx], y[test_idx]
        base = _baseline_rate(y_test)
        if train_idx is None:
            earlier = np.arange(0, test_idx[0] - EMBARGO_BARS_V2)
            if len(earlier) < 800:
                continue
            tr = earlier
            kind = "final_eval"
        else:
            tr = train_idx
            kind = "walk_forward"

        # --- RandomForest ---
        scaler = StandardScaler().fit(X[tr])
        clf = RandomForestClassifier(
            n_estimators=cfg.n_estimators,
            max_depth=cfg.max_depth,
            min_samples_leaf=cfg.min_samples_leaf,
            class_weight="balanced",
            random_state=cfg.random_state,
            n_jobs=-1,
        ).fit(scaler.transform(X[tr]), y[tr])
        rep = {"kind": kind, "model": "rf"}
        rep.update(_fold_metrics(y_test, clf.predict(scaler.transform(X_test)), base))
        fold_reports.append(rep)

        # --- DNN ---
        if cfg.train_dnn and have_torch:
            split = max(int(len(tr) * 0.9), 1)
            tr_fit, tr_val = tr[:split], tr[split:]
            if len(tr_val) >= 200:
                got = _train_dnn(X[tr_fit], y[tr_fit], X[tr_val], y[tr_val], cfg)
                if got is not None:
                    model, dsc, _val_acc = got
                    drep = {"kind": kind, "model": "dnn"}
                    drep.update(_fold_metrics(y_test, _dnn_predict(model, dsc, X_test), base))
                    dnn_fold_reports.append(drep)

    rf_eval = [r for r in fold_reports if r["kind"] == "final_eval"]
    if not rf_eval:
        raise ValueError("no final evaluation window produced")
    ev = rf_eval[-1]

    # Refit final production RF on everything (documented, deliberate).
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
    joblib.dump({
        "scaler": final_scaler,
        "clf": final_clf,
        "feature_names": CHANNEL_NAMES,
        "geometry": {
            "window_len": WINDOW_LEN,
            "channels": N_CHANNELS,
            "label_horizon": LABEL_HORIZON_V2,
            "k_up": cfg.k_up,
            "k_down": cfg.k_down,
            "embargo_bars": EMBARGO_BARS_V2,
        },
    }, out_dir / "model.joblib")

    dnn_final = None
    if cfg.train_dnn and have_torch:
        split = int(len(X) * 0.9)
        got = _train_dnn(X[:split], y[:split], X[split:], y[split:], cfg)
        if got is not None:
            model, dsc, holdout_acc = got
            import torch
            torch.save({"state_dict": model.state_dict(),
                        "hidden": cfg.dnn_hidden,
                        "in_dim": X.shape[1]}, out_dir / "dnn.pt")
            joblib.dump(dsc, out_dir / "dnn_scaler.joblib")
            dnn_final = {"holdout_val_accuracy": round(holdout_acc, 4),
                         "note": "holdout = tail of training data, NOT the final eval window"}

    dnn_eval = [r for r in dnn_fold_reports if r["kind"] == "final_eval"]

    metrics = {
        "schema": "ml-train-metrics/v2",
        "model": cfg.name,
        "samples": int(len(X)),
        "label_counts": asdict(counts),
        "positive_rate": round(float(np.mean(y == 1)), 4),
        "global_majority_baseline": round(_baseline_rate(y), 4),
        "rf_folds": fold_reports,
        "dnn_folds": dnn_fold_reports,
        "rf_final_eval": ev,
        "dnn_final_eval": dnn_eval[-1] if dnn_eval else None,
        "dnn_holdout": dnn_final,
        "torch_available": bool(have_torch),
        "config": asdict(cfg),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    manifest = {
        "schema": "ml-manifest/v2",
        "model": cfg.name,
        "config": asdict(cfg),
        "data_file": csv_path.name,
        "data_sha256": _file_sha256(csv_path),
        "candles_loaded": len(candles),
        "python": platform.python_version(),
        "sklearn": __import__("sklearn").__version__,
        "numpy": np.__version__,
        "torch": (__import__("torch").__version__ if have_torch else None),
        "generated_utc": metrics["generated_utc"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return metrics
