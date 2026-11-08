"""Broker server clock model.

MetaTrader stores bar and tick timestamps in **server** time, and the server
follows European DST (UTC+2 winter, UTC+3 summer). A single measured offset is
therefore wrong for half the year: history collected before the last switch
would be shifted by one hour, which reads as a fake hourly gap every day.

The rule is modelled rather than measured per timestamp, and the measured offset
at attach time must agree with the model or the run is blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

WINTER_OFFSET_S = 2 * 3600
SUMMER_OFFSET_S = 3 * 3600


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    day = nxt - timedelta(days=1)
    while day.weekday() != weekday:
        day -= timedelta(days=1)
    return day


def eu_dst_bounds(year: int) -> tuple[datetime, datetime]:
    """EU summer time: last Sunday March 01:00 UTC → last Sunday October 01:00 UTC."""
    start = datetime.combine(_last_weekday(year, 3, 6), datetime.min.time()).replace(
        hour=1, tzinfo=timezone.utc
    )
    end = datetime.combine(_last_weekday(year, 10, 6), datetime.min.time()).replace(
        hour=1, tzinfo=timezone.utc
    )
    return start, end


@dataclass(frozen=True, slots=True)
class BrokerClock:
    winter_offset_s: int = WINTER_OFFSET_S
    summer_offset_s: int = SUMMER_OFFSET_S

    def offset_for(self, dt_utc: datetime) -> int:
        start, end = eu_dst_bounds(dt_utc.astimezone(timezone.utc).year)
        moment = dt_utc.astimezone(timezone.utc)
        return self.summer_offset_s if start <= moment < end else self.winter_offset_s

    def to_utc(self, server_epoch_s: float) -> datetime:
        """Convert a server-time epoch to UTC, resolving the offset it was stored with."""
        naive = datetime.fromtimestamp(server_epoch_s, tz=timezone.utc)
        first = naive - timedelta(seconds=self.offset_for(naive))
        offset = self.offset_for(first)
        result = datetime.fromtimestamp(server_epoch_s - offset, tz=timezone.utc)
        refined = self.offset_for(result)
        if refined != offset:
            result = datetime.fromtimestamp(server_epoch_s - refined, tz=timezone.utc)
        return result

    def matches(self, measured_offset_s: int, now_utc: datetime, tolerance_s: int = 90) -> bool:
        return abs(self.offset_for(now_utc) - measured_offset_s) <= tolerance_s
