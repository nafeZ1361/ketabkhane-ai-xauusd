"""S5 CLI: persist ``ema_cross_v1`` signals from stored bars.

    python scripts/signals.py [--db data/guardian.sqlite3] [--symbol XAUUSD.] [--now 2026-11-05T20:00:00+00:00]

Machine-readable single-line JSON on stdout; diagnostics on stderr.
Exit codes: 0 success, 1 domain failure, 2 invalid arguments.

No MT5 import, no terminal, no order path.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.application.signal_service import DEFAULT_SYMBOL, SignalService  # noqa: E402
from guardian.contracts.signals import SignalError  # noqa: E402
from guardian.storage.db import apply_migrations, connect  # noqa: E402


def _aware_timestamp(text: str) -> datetime:
    """argparse type: an ISO-8601 timestamp that carries a real UTC offset."""
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 timestamp: {text!r}") from exc
    if moment.tzinfo is None:
        raise argparse.ArgumentTypeError("--now must be timezone-aware (include an offset)")
    try:
        offset = moment.utcoffset()
    except (TypeError, ValueError, OverflowError) as exc:
        raise argparse.ArgumentTypeError("--now must have a valid UTC offset") from exc
    if offset is None:
        raise argparse.ArgumentTypeError("--now must have a valid UTC offset")
    return moment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persist ema_cross_v1 signals from stored bars.")
    parser.add_argument("--db", default=str(ROOT / "data" / "guardian.sqlite3"), help="SQLite database path")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="symbol to evaluate")
    parser.add_argument(
        "--now",
        type=_aware_timestamp,
        default=None,
        help="evaluation instant, ISO-8601 with offset (default: current UTC)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    moment = args.now if args.now is not None else datetime.now(timezone.utc)

    conn = None
    try:
        conn = connect(args.db)
        apply_migrations(conn, ROOT / "migrations")
        outcome = SignalService(conn, symbol=args.symbol).run(now=moment)
        payload = {
            "status": "OK",
            "run_id": outcome.run.run_id,
            "symbol": args.symbol,
            "timeframe": outcome.run.timeframe,
            "strategy_id": outcome.run.strategy_id,
            "from_utc": outcome.run.from_utc.isoformat(),
            "to_utc": outcome.run.to_utc.isoformat(),
            "bars_seen": outcome.run.bars_seen,
            "signals": outcome.run.signals,
            "written": outcome.written,
            "identical": outcome.identical,
            "created": outcome.created,
            "bars_digest": outcome.bars_digest,
        }
        print(json.dumps(payload, separators=(",", ":"), sort_keys=True))
        return 0
    except SignalError as exc:
        print(json.dumps({"status": "FAILED", "error": "SignalError", "detail": str(exc)}, sort_keys=True))
        return 1
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "error": type(exc).__name__, "detail": str(exc)}, sort_keys=True))
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
