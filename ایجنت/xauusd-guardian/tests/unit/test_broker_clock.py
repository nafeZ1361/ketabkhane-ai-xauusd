"""Broker clock: EU DST model and server→UTC conversion."""

from __future__ import annotations

from datetime import datetime, timezone

from guardian.domain.market.broker_clock import BrokerClock, eu_dst_bounds


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


CLOCK = BrokerClock()


def test_eu_dst_bounds_2026():
    start, end = eu_dst_bounds(2026)
    assert start == utc(2026, 3, 29, 1, 0)   # last Sunday of March
    assert end == utc(2026, 10, 25, 1, 0)    # last Sunday of October


def test_summer_and_winter_offsets():
    assert CLOCK.offset_for(utc(2026, 7, 1, 12, 0)) == 10800
    assert CLOCK.offset_for(utc(2026, 1, 15, 12, 0)) == 7200


def test_summer_bar_converts_with_three_hours():
    # 12:00 server on 2026-07-01 is 09:00 UTC
    epoch = utc(2026, 7, 1, 12, 0).timestamp()
    assert CLOCK.to_utc(epoch) == utc(2026, 7, 1, 9, 0)


def test_winter_bar_converts_with_two_hours():
    epoch = utc(2026, 12, 1, 12, 0).timestamp()
    assert CLOCK.to_utc(epoch) == utc(2026, 12, 1, 10, 0)


def test_switch_day_is_resolved_on_the_utc_side():
    # 2026-10-25 01:00 UTC is the switch; 03:30 server is +2 (winter) → 01:30 UTC
    after = utc(2026, 10, 25, 3, 30).timestamp()
    assert CLOCK.to_utc(after) == utc(2026, 10, 25, 1, 30)
