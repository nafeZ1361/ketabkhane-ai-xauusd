"""Pure market-data validation. No I/O, no MT5 import.

Returns a verdict, never raises for bad data: a broken series is evidence, not
an exception.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from guardian.contracts.market import (
    DataQualityReport,
    MarketBar,
    MarketTick,
    QualityStatus,
    Timeframe,
)
from guardian.domain.market.session import SessionCalendar


def _finite(*values: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in values)


def check_bar(bar: MarketBar) -> str | None:
    """Return a reason string when a single bar is unusable."""
    if not _finite(bar.open, bar.high, bar.low, bar.close):
        return "non_finite_price"
    if min(bar.open, bar.high, bar.low, bar.close) <= 0:
        return "non_positive_price"
    if bar.high < bar.low:
        return "high_below_low"
    if bar.high < max(bar.open, bar.close):
        return "high_below_body"
    if bar.low > min(bar.open, bar.close):
        return "low_above_body"
    return None


def check_tick(tick: MarketTick) -> str | None:
    if not _finite(tick.bid, tick.ask):
        return "non_finite_price"
    if tick.bid <= 0 or tick.ask <= 0:
        return "non_positive_price"
    if tick.bid > tick.ask:
        return "crossed_quote"
    return None


def validate_bars(
    bars: Sequence[MarketBar],
    *,
    calendar: SessionCalendar,
    now_utc: datetime,
    gap_tolerance_bars: int = 1,
    stale_after_bars: int = 2,
    min_bars_ratio: float = 0.5,
) -> DataQualityReport:
    """Full quality verdict for one fetched series."""
    symbol = bars[0].symbol if bars else "?"
    timeframe = bars[0].timeframe if bars else Timeframe.M1

    if not bars:
        return DataQualityReport(
            symbol=symbol,
            timeframe=timeframe,
            status=QualityStatus.FAILED,
            reasons=("empty_series",),
        )

    reasons: list[str] = []
    invalid = 0
    duplicates = 0
    ordered: list[MarketBar] = []
    seen: set[datetime] = set()

    previous: datetime | None = None
    non_monotonic = 0
    for bar in bars:
        if bar.time_utc in seen:
            duplicates += 1
            continue
        seen.add(bar.time_utc)
        if previous is not None and bar.time_utc < previous:
            non_monotonic += 1
            continue
        previous = bar.time_utc
        if check_bar(bar) is not None:
            invalid += 1
            continue
        ordered.append(bar)

    if non_monotonic:
        return DataQualityReport(
            symbol=symbol,
            timeframe=timeframe,
            status=QualityStatus.BLOCKED,
            received_bars=len(bars),
            invalid_bars=invalid,
            duplicates=duplicates,
            reasons=(f"non_monotonic_time:{non_monotonic}",),
        )

    if not ordered:
        return DataQualityReport(
            symbol=symbol,
            timeframe=timeframe,
            status=QualityStatus.BLOCKED,
            received_bars=len(bars),
            invalid_bars=invalid,
            duplicates=duplicates,
            reasons=("no_valid_bars",),
        )

    first, last = ordered[0].time_utc, ordered[-1].time_utc
    expected = calendar.expected_bars(timeframe.minutes, first, last + timedelta(minutes=timeframe.minutes))

    ratio = len(ordered) / expected if expected else 1.0
    if expected and ratio < min_bars_ratio:
        return DataQualityReport(
            symbol=symbol,
            timeframe=timeframe,
            status=QualityStatus.BLOCKED,
            expected_bars=expected,
            received_bars=len(ordered),
            invalid_bars=invalid,
            duplicates=duplicates,
            first_utc=first,
            last_utc=last,
            reasons=(f"DAILY_RESOLUTION_DETECTED:ratio={ratio:.3f}",),
        )

    # Gaps: expected boundary missing for more than ``gap_tolerance_bars`` in a row.
    gaps = 0
    max_run = 0
    run = 0
    gap_details: list[tuple[datetime, int]] = []
    run_start: datetime | None = None
    cursor = first
    step = timedelta(minutes=timeframe.minutes)
    half = timedelta(minutes=timeframe.minutes / 2)
    index = {bar.time_utc for bar in ordered}
    while cursor <= last:
        if calendar.is_open(cursor + half):
            if cursor in index:
                if run > gap_tolerance_bars:
                    gaps += 1
                    max_run = max(max_run, run)
                    if run_start is not None:
                        gap_details.append((run_start, run))
                run = 0
                run_start = None
            else:
                if run == 0:
                    run_start = cursor
                run += 1
        elif run:
            # the market closed: a hole cannot span a closure
            if run > gap_tolerance_bars:
                gaps += 1
                max_run = max(max_run, run)
                if run_start is not None:
                    gap_details.append((run_start, run))
            run = 0
            run_start = None
        cursor += step
    if run > gap_tolerance_bars:
        gaps += 1
        max_run = max(max_run, run)
        if run_start is not None:
            gap_details.append((run_start, run))

    stale = False
    if calendar.is_open(now_utc):
        age = now_utc - (last + step)
        if age > stale_after_bars * step:
            stale = True

    status = QualityStatus.OK
    if gaps:
        reasons.append(f"gaps:{gaps}")
        status = QualityStatus.DEGRADED
    if max_run:
        reasons.append(f"max_gap_bars:{max_run}")
    if duplicates:
        reasons.append(f"duplicates:{duplicates}")
    if invalid:
        reasons.append(f"invalid_bars:{invalid}")
        status = QualityStatus.DEGRADED
    if duplicates:
        status = QualityStatus.DEGRADED
    if stale:
        reasons.append("STALE_FEED")
        status = QualityStatus.DEGRADED

    return DataQualityReport(
        symbol=symbol,
        timeframe=timeframe,
        status=status,
        expected_bars=expected,
        received_bars=len(ordered),
        duplicates=duplicates,
        invalid_bars=invalid,
        gaps=gaps,
        max_gap_bars=max_run,
        gap_details=tuple(gap_details),
        first_utc=first,
        last_utc=last,
        reasons=tuple(reasons),
    )


def count_crossed_quotes(ticks: Iterable[MarketTick]) -> int:
    return sum(1 for tick in ticks if check_tick(tick) == "crossed_quote")


def dedupe_ticks(ticks: Iterable[MarketTick]) -> list[MarketTick]:
    """Dedupe on the documented key: (symbol, time_msc, bid, ask)."""
    seen: set[tuple[str, int, float, float]] = set()
    out: list[MarketTick] = []
    for tick in ticks:
        key = (tick.symbol, tick.time_msc, tick.bid, tick.ask)
        if key in seen:
            continue
        seen.add(key)
        out.append(tick)
    return out


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
