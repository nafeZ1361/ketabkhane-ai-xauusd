"""Session calendar: weekend, daily halt, DST, expected bar counts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from guardian.domain.market.session import SessionCalendar, dst_bounds_utc


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


CAL = SessionCalendar()


def test_wednesday_midday_is_open():
    assert CAL.is_open(utc(2026, 11, 4, 16, 0)) is True  # 11:00 ET


def test_saturday_is_closed():
    assert CAL.is_open(utc(2026, 11, 7, 15, 0)) is False


def test_sunday_before_open_is_closed_and_after_is_open():
    assert CAL.is_open(utc(2026, 11, 8, 22, 0)) is False  # 17:00 EST
    assert CAL.is_open(utc(2026, 11, 8, 23, 30)) is True  # 18:30 EST


def test_friday_after_close_is_closed():
    assert CAL.is_open(utc(2026, 11, 6, 21, 30)) is True   # 16:30 EST
    assert CAL.is_open(utc(2026, 11, 6, 22, 30)) is False  # 17:30 EST


def test_daily_halt_summer_is_2100_to_2200_utc():
    # 2026-07-15 is EDT (-4): 17:00-18:00 ET == 21:00-22:00Z
    assert CAL.is_open(utc(2026, 7, 15, 20, 30)) is True
    assert CAL.is_open(utc(2026, 7, 15, 21, 30)) is False
    assert CAL.is_break(utc(2026, 7, 15, 21, 30)) is True


def test_daily_halt_winter_is_2200_to_2300_utc():
    assert CAL.is_open(utc(2026, 12, 15, 21, 30)) is True
    assert CAL.is_open(utc(2026, 12, 15, 22, 30)) is False


def test_dst_bounds_follow_the_us_rule():
    start, end = dst_bounds_utc(2026)
    assert start == utc(2026, 3, 8, 7, 0)   # 02:00 EST
    assert end == utc(2026, 11, 1, 6, 0)    # 02:00 EDT


def test_offset_switches_across_dst():
    assert CAL.offset_hours(utc(2026, 7, 1, 12, 0)) == -4
    assert CAL.offset_hours(utc(2026, 12, 1, 12, 0)) == -5


def test_expected_bars_for_a_fully_open_hour():
    assert CAL.expected_bars(1, utc(2026, 11, 4, 14, 0), utc(2026, 11, 4, 15, 0)) == 60


def test_expected_bars_excludes_the_daily_halt():
    # 16:00-18:00 ET on a summer Wednesday: one open hour
    assert CAL.expected_bars(1, utc(2026, 7, 15, 20, 0), utc(2026, 7, 15, 22, 0)) == 60


def test_expected_bars_is_zero_over_the_weekend():
    assert CAL.expected_bars(1, utc(2026, 11, 7, 0, 0), utc(2026, 11, 8, 0, 0)) == 0


def test_unknown_anchor_is_rejected():
    with pytest.raises(ValueError, match="anchor"):
        SessionCalendar(anchor="Europe/London")


def test_expected_bars_rejects_oversized_spans():
    with pytest.raises(ValueError, match="too large"):
        CAL.expected_bars(1, utc(2020, 1, 1), utc(2026, 1, 1))
