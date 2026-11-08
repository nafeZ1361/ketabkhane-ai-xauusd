"""Apply or lift a reversible run quarantine. Never deletes or rewrites data.

    python scripts/quarantine.py status
    python scripts/quarantine.py apply --run-id e01f... --reason "request window pre-A2"
    python scripts/quarantine.py restore --run-id e01f...

A quarantined run keeps every row and its original status in ``audit_events``;
``MarketStore.health`` and every market-data read exclude it while the status is
``QUARANTINED``. Restoration is exact because the previous status is recorded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.config.settings import load_settings  # noqa: E402
from guardian.storage.db import apply_migrations, connect  # noqa: E402
from guardian.storage.market_store import MarketStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="reversible run quarantine")
    parser.add_argument("action", choices=("apply", "restore", "status"))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--reason", default="operator quarantine")
    parser.add_argument("--db", default="")
    args = parser.parse_args(argv)

    settings = load_settings(ROOT / "configs" / "config.toml")
    md = settings.market_data
    db_path = Path(args.db) if args.db else ROOT / (md.data_root if md else "data") / "guardian.sqlite3"
    if not db_path.exists():
        print(json.dumps({"error": "no database", "path": str(db_path)}))
        return 1

    conn = connect(db_path)
    apply_migrations(conn, ROOT / "migrations")
    store = MarketStore(conn, quota_bytes=int((md.tick_quota_gb if md else 2.0) * 1_000_000_000))

    if args.action == "status":
        print(
            json.dumps(
                {"db": str(db_path), "quarantined_runs": store.quarantined_runs(), "health": store.health()},
                indent=2,
                default=str,
            )
        )
        return 0

    if not args.run_id:
        print(json.dumps({"error": "--run-id is required for apply/restore"}))
        return 2

    try:
        if args.action == "apply":
            previous = store.quarantine_run(args.run_id, args.reason)
            payload = {"action": "apply", "run_id": args.run_id, "previous_status": previous, "status": "QUARANTINED"}
        else:
            restored = store.restore_run(args.run_id)
            payload = {"action": "restore", "run_id": args.run_id, "status": restored}
    except ValueError as exc:
        print(json.dumps({"error": str(exc), "run_id": args.run_id}))
        return 2

    payload["db"] = str(db_path)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
