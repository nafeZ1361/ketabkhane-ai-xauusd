"""Single-holdout edge test for XAUUSD M1 bars (70/30 chronological split).

Deliberately unglamorous: features at bar t use only bars <= t, the split is
chronological, and the headline number is the *net* forward return of the model's
signals after a spread cost. If there is no edge, this prints that.

Usage:
    python scripts/research_edge.py --csv <MT5 M1 TSV> [--bars 600000] [--horizon 15]
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

FEATURES = [
    "ret1", "ret5", "ret15", "ret60",
    "ema_gap", "rsi", "atr", "vol60", "hour", "dow",
]


def load(path: str, bars: int) -> pd.DataFrame:
    df = pd.read_csv(
        path, sep="\t", usecols=["<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>", "<CLOSE>", "<SPREAD>"],
    )
    df.columns = ["date", "time", "open", "high", "low", "close", "spread"]
    df["ts"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.drop_duplicates("ts").sort_values("ts").set_index("ts")
    if bars and len(df) > bars:
        df = df.iloc[-bars:]
    return df[["open", "high", "low", "close", "spread"]].astype("float64")


def features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]
    out = pd.DataFrame(index=df.index)
    out["ret1"] = c.pct_change(1)
    out["ret5"] = c.pct_change(5)
    out["ret15"] = c.pct_change(15)
    out["ret60"] = c.pct_change(60)
    ema20, ema50 = c.ewm(span=20, adjust=False).mean(), c.ewm(span=50, adjust=False).mean()
    out["ema_gap"] = (ema20 - ema50) / c
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - c.shift()).abs(),
                    (df["low"] - c.shift()).abs()], axis=1).max(axis=1)
    out["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean() / c
    out["vol60"] = out["ret1"].rolling(60).std()
    out["hour"] = df.index.hour
    out["dow"] = df.index.dayofweek
    return out


def forward_label(df: pd.DataFrame, horizon_minutes: int) -> tuple[pd.Series, pd.Series]:
    """Forward return to the first bar at or after ``signal_time + horizon``.

    The horizon is a duration, not a row count. On M1 data the two differ across
    weekends, holidays and missing bars, so ``shift(-n)`` is wrong by construction.
    A row whose target lies beyond the data gets NaN and is excluded downstream.
    """
    stamps = df.index.values
    target = stamps + np.timedelta64(int(horizon_minutes), "m")
    pos = np.searchsorted(stamps, target, side="left")
    valid = pos < len(stamps)
    clipped = np.clip(pos, 0, len(stamps) - 1)
    close = df["close"].to_numpy(dtype=float)
    forward = np.where(valid, close[clipped] / close - 1.0, np.nan)
    label_time = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    label_time.loc[valid] = df.index[clipped[valid]]
    return pd.Series(forward, index=df.index), label_time


def purged_split(
    df: pd.DataFrame,
    label_time: pd.Series,
    horizon_minutes: int,
    test_fraction: float = 0.7,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Chronological split with a purge and a one-horizon embargo.

    A training row is kept only if its label is complete *and* its label window ends
    before ``test_start - horizon``. Purging only the rows whose label crosses the
    boundary is not enough: labels sampled every bar overlap, so the embargo keeps
    the last horizon of training away from the test period.
    """
    n = len(df)
    split = int(n * test_fraction)
    test_start = df.index[split]
    embargo = pd.Timedelta(minutes=int(horizon_minutes))

    position = np.arange(n)
    in_train = position < split
    invalid = label_time.isna().to_numpy()
    stamps = label_time.to_numpy()

    boundary = in_train & ~invalid & (stamps >= np.datetime64(test_start))
    kept_before_embargo = in_train & ~invalid & ~boundary
    embargoed = kept_before_embargo & (stamps >= np.datetime64(test_start - embargo))
    train_mask = kept_before_embargo & ~embargoed
    test_mask = ~in_train

    stats = {
        "raw": n,
        "invalid": int((invalid & in_train).sum()),
        "train_dropped_boundary": int(boundary.sum()),
        "train_dropped_embargo": int(embargoed.sum()),
        "final_train": int(train_mask.sum()),
        "test": int(test_mask.sum()),
        "embargo": "1x horizon",
        "test_start_server": str(test_start),  # MT5 server time (UTC+2/+3), not UTC
    }
    return train_mask, test_mask, stats


def run(csv: str, bars: int, horizon: int, cost: float) -> int:
    df = load(csv, bars)
    x = features(df)
    fwd, label_time = forward_label(df, horizon)
    y = (fwd > 0).astype(int)
    data = x.assign(fwd=fwd, y=y, label_time=label_time).dropna()
    if len(data) < 20_000:
        print("not enough rows after warmup:", len(data))
        return 1

    train_mask, test_mask, split_stats = purged_split(data, data["label_time"], horizon)
    train, test = data[train_mask], data[test_mask]
    print("split accounting:", {k: v for k, v in split_stats.items() if k != "embargo"},
          "(embargo = 1x horizon; timestamps are MT5 server time, UTC+2/+3, not UTC)")
    print(f"rows={len(data)} train={len(train)} test={len(test)} horizon={horizon}m cost={cost}")
    print(f"base rate (test) = {test['y'].mean():.3f}")

    models = {
        "logistic": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        "tree(d=4)": DecisionTreeClassifier(max_depth=4, min_samples_leaf=500, random_state=7),
        "hgb": HistGradientBoostingClassifier(max_iter=200, max_depth=4, random_state=7),
    }
    for name, model in models.items():
        model.fit(train[FEATURES], train["y"])
        p = model.predict_proba(test[FEATURES])[:, 1]
        auc = roc_auc_score(test["y"], p)
        long_mask = p > 0.55
        n = int(long_mask.sum())
        gross = float(test.loc[long_mask, "fwd"].mean()) if n else 0.0
        net = gross - cost
        print(f"{name:10s} AUC={auc:.4f} signals={n:6d} ({n / len(test):.1%}) "
              f"gross/trade={gross:+.5%} net/trade={net:+.5%}")
    print("\nreference: mean forward return of every test bar (overlapping, not buy-and-hold)")
    print(f"  gross/trade={test['fwd'].mean():+.5%} net/trade={test['fwd'].mean() - cost:+.5%}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--bars", type=int, default=600_000)
    ap.add_argument("--horizon", type=int, default=15)
    ap.add_argument("--cost", type=float, default=0.0002, help="round-trip cost as a return")
    a = ap.parse_args()
    return run(a.csv, a.bars, a.horizon, a.cost)


if __name__ == "__main__":
    sys.exit(main())
