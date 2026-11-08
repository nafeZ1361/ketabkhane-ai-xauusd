"""Exchange session calendar for XAUUSD (CME-style gold hours).

Anchored to exchange time (America/New_York), not fixed UTC: the daily halt and
the Sunday open shift by one hour across DST. The 2007+ US DST rule is computed
in code, so no ``tzdata`` package is required.

Hours modelled: Sunday 18:00 ET open, Friday 17:00 ET close, Mon–Thu halt
17:00–18:00 ET.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

ANCHOR_TZ = "America/New_York"
SUPPORTED_ANCHORS = (ANCHOR_TZ,)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th ``weekday`` (Mon=0) of a month."""
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    return date(year, month, 1 + delta + 7 * (n - 1))


def dst_bounds_utc(year: int) -> tuple[datetime, datetime]:
    """US DST for ``year`` in UTC: 2nd Sunday Mar 02:00 EST → 1st Sunday Nov 02:00 EDT."""
    start_local = datetime.combine(_nth_weekday(year, 3, 6, 2), time(2, 0))
    end_local = datetime.combine(_nth_weekday(year, 11, 6, 1), time(2, 0))
    return (
        (start_local + timedelta(hours=5)).replace(tzinfo=timezone.utc),
        (end_local + timedelta(hours=4)).replace(tzinfo=timezone.utc),
    )


@dataclass(frozen=True, slots=True)
class SessionCalendar:
    week_open_hour: int = 18  # Sunday
    week_close_hour: int = 17  # Friday
    break_start_hour: int = 17  # Mon–Thu
    break_end_hour: int = 18
    anchor: str = ANCHOR_TZ
    week_open_weekday: int = 6  # Sunday
    week_close_weekday: int = 4  # Friday

    def __post_init__(self) -> None:
        if self.anchor not in SUPPORTED_ANCHORS:
            raise ValueError(f"unsupported anchor timezone: {self.anchor!r}")

    # -- time conversion ---------------------------------------------------
    def offset_hours(self, dt_utc: datetime) -> int:
        start, end = dst_bounds_utc(dt_utc.year)
        return -4 if start <= dt_utc < end else -5

    def to_exchange(self, dt_utc: datetime) -> datetime:
        if dt_utc.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return dt_utc.astimezone(timezone.utc) + timedelta(hours=self.offset_hours(dt_utc))

    # -- session rules -----------------------------------------------------
    def is_open(self, dt_utc: datetime) -> bool:
        local = self.to_exchange(dt_utc)
        wd = local.weekday()  # Mon=0 … Sun=6
        hour = local.hour
        if wd == 5:  # Saturday
            return False
        if wd == self.week_open_weekday:  # Sunday
            return hour >= self.week_open_hour
        if wd == self.week_close_weekday:  # Friday
            return hour < self.week_close_hour
        return not (self.break_start_hour <= hour < self.break_end_hour)

    def is_break(self, dt_utc: datetime) -> bool:
        local = self.to_exchange(dt_utc)
        return local.weekday() in (0, 1, 2, 3) and self.break_start_hour <= local.hour < self.break_end_hour

    # -- expectations ------------------------------------------------------
    def expected_bars(self, tf_minutes: int, start_utc: datetime, end_utc: datetime) -> int:
        """Count timeframe boundaries in ``[start, end)`` that fall inside a session.

        Uses the bar midpoint so a bar straddling a boundary is not counted twice.
        Guarded against pathological spans (max 500 000 iterations).
        """
        if tf_minutes <= 0:
            raise ValueError("tf_minutes must be positive")
        if start_utc.tzinfo is None or end_utc.tzinfo is None:
            raise ValueError("datetimes must be timezone-aware")
        start = start_utc.astimezone(timezone.utc)
        end = end_utc.astimezone(timezone.utc)
        if end <= start:
            return 0

        step = timedelta(minutes=tf_minutes)
        half = timedelta(minutes=tf_minutes / 2)
        cursor = start
        count = 0
        iterations = 0
        while cursor < end:
            iterations += 1
            if iterations > 500_000:
                raise ValueError("span too large for expected_bars; narrow the window")
            if self.is_open(cursor + half):
                count += 1
            cursor += step
        return count

    def expected_bars_last_days(self, tf_minutes: int, now_utc: datetime, days: int) -> int:
        return self.expected_bars(tf_minutes, now_utc - timedelta(days=days), now_utc)

    def describe(self) -> str:
        return (
            f"{self.anchor}: sun {self.week_open_hour:02d}:00 → fri {self.week_close_hour:02d}:00, "
            f"halt {self.break_start_hour:02d}:00–{self.break_end_hour:02d}:00 Mon–Thu"
        )
