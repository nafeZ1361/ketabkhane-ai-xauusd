import statistics
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from guardian.contracts.market import MarketBar, Timeframe
from guardian.storage.db import apply_migrations, connect
from guardian.storage.market_store import MarketStore

MIG = Path(__file__).resolve().parents[1] / "migrations"


def run(n: int = 3000) -> float:
    td = tempfile.mkdtemp()
    if True:
        conn = connect(Path(td) / "b.sqlite3")
        apply_migrations(conn, MIG)
        store = MarketStore(conn, quota_bytes=10**9)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        bars = [
            MarketBar("XAUUSD.", Timeframe.M1, start + timedelta(minutes=i),
                      1.0 + i, 2.0 + i, 0.5 + i, 1.5 + i, 10, 5, 0.0)
            for i in range(n)
        ]
        t0 = time.perf_counter()
        store.upsert_bars("bench-run", bars)
        elapsed = time.perf_counter() - t0
    conn.close()
    return elapsed


if __name__ == "__main__":
    times = [run() for _ in range(3)]
    print("runs", [round(x, 3) for x in times],
          "median", round(statistics.median(times), 3))
