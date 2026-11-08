"""Collect market data (read-only). Never touches an order API.

    python scripts/collect.py --bars M1,M5 --count 5000
    python scripts/collect.py --ticks-minutes 30
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from guardian.adapters.mt5_market import Mt5MarketAdapter  # noqa: E402
from guardian.application.market_data_service import (  # noqa: E402
    CollectionOutcome,
    MarketDataService,
    MarketRunConfig,
)
from guardian.config.settings import ConfigError, load_settings  # noqa: E402
from guardian.contracts.market import Timeframe  # noqa: E402
from guardian.domain.market.session import SessionCalendar  # noqa: E402
from guardian.storage.db import apply_migrations, connect  # noqa: E402
from guardian.storage.market_store import MarketStore  # noqa: E402

EXIT = {"OK": 0, "DEGRADED": 0, "BLOCKED": 2, "FAILED": 1, "CONNECTION_FAILED": 1}


def parse_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp that must carry a zone; return UTC."""
    text = value.strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid UTC timestamp: {value!r}") from exc
    if moment.tzinfo is None:
        raise argparse.ArgumentTypeError(f"timestamp needs a UTC offset or Z: {value!r}")
    return moment.astimezone(timezone.utc)


def resolve_tick_window(
    *, start: datetime | None, end: datetime | None, minutes: int, now: datetime
) -> tuple[datetime, datetime]:
    """Resolve the tick window. Explicit bounds are never mixed with the relative form.

    An explicitly supplied end is never replaced by ``now``, and a reversed or
    empty window is refused instead of being silently corrected.
    """
    if (start is None) != (end is None):
        raise ValueError("--ticks-start and --ticks-end must be given together")
    if start is not None:
        if minutes:
            raise ValueError("--ticks-minutes cannot be combined with --ticks-start/--ticks-end")
        assert end is not None
        if end < start:
            raise ValueError("tick window end is before start")
        if end == start:
            raise ValueError("tick window is empty")
        return start, end
    if minutes < 0:
        raise ValueError("--ticks-minutes must not be negative")
    span = minutes or 30
    return now - timedelta(minutes=span), now


def effective_status(outcome: CollectionOutcome) -> tuple[str, list[str]]:
    """A tick run that inserted no row is a failure, whatever the service reported."""
    reasons = list(outcome.reasons)
    if (
        outcome.runs
        and all(run.kind == "ticks" for run in outcome.runs)
        and outcome.status in ("OK", "DEGRADED")
        and sum(run.inserted for run in outcome.runs) == 0
    ):
        reasons.append("inserted_zero:no_new_rows")
        return "FAILED", reasons
    return outcome.status, reasons


def build_service(settings, db_path: Path) -> tuple[MarketDataService, MarketStore]:
    md = settings.market_data
    if md is None:
        raise ConfigError("[market_data] section is required for collection")
    conn = connect(db_path)
    apply_migrations(conn, ROOT / "migrations")
    store = MarketStore(conn, quota_bytes=int(md.tick_quota_gb * 1_000_000_000))
    calendar = SessionCalendar(
        week_open_hour=md.session.week_open_hour,
        week_close_hour=md.session.week_close_hour,
        break_start_hour=md.session.break_start_hour,
        break_end_hour=md.session.break_end_hour,
        anchor=md.session.anchor,
    )
    profile = settings.symbol_expectations
    from guardian.domain.symbols import GoldExpectations

    expectations = (
        GoldExpectations()
        if profile is None
        else GoldExpectations(
            schema_version=profile.schema_version,
            aliases=profile.aliases,
            required_symbol_name=profile.required_symbol_name,
            required_path_token=profile.required_path_token,
            required_profit_currency=profile.required_profit_currency,
            contract_size=profile.contract_size,
            tick_size=profile.tick_size,
            digits=profile.digits,
            require_full_trade_mode=profile.require_full_trade_mode,
        )
    )
    config = MarketRunConfig(
        policy=settings.execution.symbol_policy,
        expectations=expectations,
        expected_server=settings.account.expected_server,
        expected_currency=settings.account.currency,
        expected_trade_mode=settings.account.expected_trade_mode,
        expected_company=settings.account.expected_company,
        gap_tolerance_bars=md.gap_tolerance_bars,
        stale_after_bars=md.stale_after_bars,
        min_bars_ratio=md.min_bars_per_day,
        max_tick_window_h=md.max_tick_window_h,
    )
    return MarketDataService(Mt5MarketAdapter(), store, calendar, config), store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", default="", help="comma separated timeframes, e.g. M1,M5,H1")
    parser.add_argument("--count", type=int, default=5000)
    parser.add_argument("--ticks-minutes", type=int, default=0)
    parser.add_argument("--ticks-start", type=parse_utc, default=None, help="explicit UTC window start (ISO-8601)")
    parser.add_argument("--ticks-end", type=parse_utc, default=None, help="explicit UTC window end (ISO-8601)")
    parser.add_argument("--db", default="")
    args = parser.parse_args()

    settings = load_settings(ROOT / "configs" / "config.toml")
    md = settings.market_data
    db_path = Path(args.db) if args.db else ROOT / (md.data_root if md else "data") / "guardian.sqlite3"

    # Usage validation happens before any file is opened, so a bad command line
    # never creates or migrates a database.
    if args.bars and (args.ticks_start or args.ticks_end):
        parser.error("--bars cannot be combined with --ticks-start/--ticks-end")
    window = None
    if not args.bars:
        try:
            window = resolve_tick_window(
                start=args.ticks_start, end=args.ticks_end, minutes=args.ticks_minutes,
                now=datetime.now(timezone.utc),
            )
        except ValueError as exc:
            parser.error(str(exc))
            raise AssertionError("unreachable")  # parser.error exits

    service, _store = build_service(settings, db_path)

    if args.bars:
        timeframes = [Timeframe(name.strip()) for name in args.bars.split(",") if name.strip()]
        outcome: CollectionOutcome = service.collect_bars(timeframes, args.count)
    else:
        assert window is not None
        start_utc, end_utc = window
        outcome = service.collect_ticks(start_utc, end_utc)

    status, reasons = effective_status(outcome)
    payload = {
        "status": status,
        "reasons": reasons,
        "runs": [
            {
                "run_id": run.run_id,
                "kind": run.kind,
                "timeframe": run.timeframe.value if run.timeframe else None,
                "status": run.status,
                "inserted": run.inserted,
                "revised": run.revised,
                "gaps": run.gaps,
                "reason": run.reason,
            }
            for run in outcome.runs
        ],
        "db": str(db_path),
    }
    print(json.dumps(payload, indent=2))
    return EXIT.get(status, 1)


if __name__ == "__main__":
    raise SystemExit(main())
