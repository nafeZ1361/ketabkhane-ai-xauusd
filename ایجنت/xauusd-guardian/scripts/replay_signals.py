"""S3 replay harness: signals from stored M5 bars, twice, digest compared.

    python scripts/replay_signals.py [--db data/guardian.sqlite3]
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


def load(path: Path) -> list[MarketBar]:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT symbol,time_utc,open,high,low,close,tick_volume,spread_points,real_volume "
        "FROM bars WHERE timeframe='M5' ORDER BY time_utc"
    ).fetchall()
    return [
        MarketBar(
            symbol=r["symbol"], timeframe=Timeframe.M5, time_utc=datetime.fromisoformat(r["time_utc"]),
            open=r["open"], high=r["high"], low=r["low"], close=r["close"],
            tick_volume=r["tick_volume"], spread_points=r["spread_points"], real_volume=r["real_volume"],
        )
        for r in rows
    ]


def digest(bars: list[MarketBar]) -> tuple[str, int]:
    h = hashlib.sha256()
    signals = evaluate(bars, now=datetime.now(timezone.utc))
    for s in signals:
        h.update(f"{s.bar_time_utc.isoformat()}|{s.direction.value}|{s.strength}|{s.reason_code}\n".encode())
    return h.hexdigest(), len(signals)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "data" / "guardian.sqlite3"))
    args = parser.parse_args()
    bars = load(Path(args.db))
    first, n1 = digest(bars)
    second, n2 = digest(bars)
    print(f"bars={len(bars)} signals={n1} digest_1={first} digest_2={second} replay_equal={first == second and n1 == n2}")
    return 0 if first == second and n1 == n2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
