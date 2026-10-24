"""Broker server-time handling.

The trading server sits in Ukraine (Europe/Kyiv: UTC+2 winter, UTC+3 summer,
EU DST rules). The data file carries naive server wall-clock timestamps, so
every candle must be converted to UTC before research.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta, timezone

UTC = timezone.utc
TEHRAN = timezone(timedelta(hours=3, minutes=30))
POLICIES = ("eu-dst", "fixed+2", "fixed+3", "utc")


class ServerTimeError(ValueError):
    """Base error for server-time conversion."""


class InvalidServerTime(ServerTimeError):
    """Local wall-clock time that does not exist (spring-forward gap)."""


class AmbiguousServerTime(ServerTimeError):
    """Local wall-clock time that occurs twice (autumn fall-back)."""


def _last_sunday(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    day = date(year, month, last_day)
    while day.weekday() != 6:
        day -= timedelta(days=1)
    return day


def dst_start(year: int) -> datetime:
    """First instant of DST in local time: last Sunday of March, 03:00."""
    return datetime.combine(_last_sunday(year, 3), time(3))


def dst_end(year: int) -> datetime:
    """First instant after DST in local time: last Sunday of October, 04:00."""
    return datetime.combine(_last_sunday(year, 10), time(4))


def eu_offset(naive: datetime) -> timedelta:
    start, end = dst_start(naive.year), dst_end(naive.year)
    return timedelta(hours=3) if start <= naive < end else timedelta(hours=2)


def to_utc(naive: datetime, policy: str = "eu-dst", allow_ambiguous: bool = False) -> datetime:
    if naive.tzinfo is not None:
        return naive.astimezone(UTC)
    if policy not in POLICIES:
        raise ValueError(f"unknown timezone policy: {policy}")
    if policy == "utc":
        return naive.replace(tzinfo=UTC)
    if policy.startswith("fixed+"):
        hours = int(policy.split("+", 1)[1])
        return (naive - timedelta(hours=hours)).replace(tzinfo=UTC)

    year = naive.year
    if dst_start(year) <= naive < dst_start(year) + timedelta(hours=1):
        raise InvalidServerTime(f"local time does not exist (spring forward): {naive}")
    ambiguous = dst_end(year) - timedelta(hours=1) <= naive < dst_end(year)
    if ambiguous and not allow_ambiguous:
        raise AmbiguousServerTime(f"local time occurs twice (fall back): {naive}")
    offset = timedelta(hours=2) if ambiguous else eu_offset(naive)
    return (naive - offset).replace(tzinfo=UTC)


def to_tehran(moment: datetime) -> datetime:
    """UTC instant in the user's reference zone (Asia/Tehran, no DST since 2022)."""
    return moment.astimezone(TEHRAN)