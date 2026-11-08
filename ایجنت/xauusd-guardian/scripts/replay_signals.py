"""S3 replay harness: signals from stored M5 bars, twice, digest compared.

    python scripts/replay_signals.py [--db data/guardian.sqlite3] [--symbol XAUUSD.]

Bars belonging to a quarantined feed run are excluded, matching the project rule
that every read of market data must exclude human-quarantined runs.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.contracts.market import MarketBar, Timeframe  # noqa: E402
from guardian.domain.strategy.ema_cross import evaluate  # noqa: E402

QUARANTINED_RUNS = "SELECT run_id FROM feed_runs WHERE status = 'QUARANTINED'"


def load(path: Path, symbol: str) -> list[MarketBar]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT symbol,time_utc,open,high,low,close,tick_volume,spread_points,real_volume "
        f"FROM bars WHERE timeframe='M5' AND symbol = ? AND run_id NOT IN ({QUARANTINED_RUNS}) "
        "ORDER BY time_utc",
        (symbol,),
    ).fetchall()
    return [
        MarketBar(
            symbol=r["symbol"], timeframe=Timeframe.M5, time_utc=datetime.fromisoformat(r["time_utc"]),
            open=r["open"], high=r["high"], low=r["low"], close=r["close"],
            tick_volume=r["tick_volume"], spread_points=r["spread_points"], real_volume=r["real_volume"],
        )
        for r in rows
    ]


def digest(bars: list[MarketBar], moment: datetime) -> tuple[str, int]:
    h = hashlib.sha256()
    signals = evaluate(bars, now=moment)
    for s in signals:
        h.update(f"{s.bar_time_utc.isoformat()}|{s.direction.value}|{s.strength}|{s.reason_code}\n".encode())
    return h.hexdigest(), len(signals)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "data" / "guardian.sqlite3"))
    parser.add_argument("--symbol", default="XAUUSD.")
    args = parser.parse_args()
    bars = load(Path(args.db), args.symbol)
    # One captured instant for both passes: a bar closing between them would flip
    # ``replay_equal`` for a reason that has nothing to do with replay.
    moment = datetime.now(timezone.utc)
    first, n1 = digest(bars, moment)
    second, n2 = digest(bars, moment)
    print(f"bars={len(bars)} signals={n1} digest_1={first} digest_2={second} replay_equal={first == second and n1 == n2}")
    return 0 if first == second and n1 == n2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
