"""Market-data health report (read-only, no terminal needed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.config.settings import load_settings  # noqa: E402
from guardian.contracts.market import Timeframe  # noqa: E402
from guardian.storage.db import apply_migrations, connect  # noqa: E402
from guardian.storage.market_store import MarketStore  # noqa: E402


def main() -> int:
    settings = load_settings(ROOT / "configs" / "config.toml")
    md = settings.market_data
    db_path = ROOT / (md.data_root if md else "data") / "guardian.sqlite3"
    if not db_path.exists():
        print(json.dumps({"error": "no database", "path": str(db_path)}))
        return 1

    conn = connect(db_path)
    apply_migrations(conn, ROOT / "migrations")
    store = MarketStore(conn, quota_bytes=int((md.tick_quota_gb if md else 2.0) * 1_000_000_000))

    report = {
        "db": str(db_path),
        "health": store.health(),
        "last_bars": {
            tf.value: store.last_bar("XAUUSD.", tf.value) for tf in Timeframe
        },
        "recent_runs": [
            dict(row)
            for row in conn.execute(
                "SELECT run_id, kind, timeframe, status, inserted, revised, gaps, started_utc "
                "FROM feed_runs ORDER BY started_utc DESC LIMIT 5"
            )
        ],
    }
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
