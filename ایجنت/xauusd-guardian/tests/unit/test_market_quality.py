"""Bar/tick quality rules: MD-03…MD-07, MD-25, MD-27."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from guardian.contracts.market import MarketBar, MarketTick, QualityStatus, Timeframe
from guardian.domain.market.quality import (
    check_bar,
    check_tick,
    dedupe_ticks,
    validate_bars,
)
from guardian.domain.market.session import SessionCalendar

CAL = SessionCalendar()
START = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)  # Wednesday, session open


def bars(n=60, *, start=START, step_min=1):
    out = []
    for i in range(n):
        t = start + timedelta(minutes=step_min * i)
        out.append(
            MarketBar(
                symbol="XAUUSD.",
                timeframe=Timeframe.M1 if step_min == 1 else Timeframe.H1,
                time_utc=t,
                open=4000 + i,
                high=4002 + i,
                low=3999 + i,
                close=4001 + i,
                tick_volume=10,
                spread_points=20,
            )
        )
    return out


def validate(series, *, now=None, **kw):
    return validate_bars(
        series,
        calendar=CAL,
        now_utc=now or START + timedelta(hours=1, minutes=1),
        **kw,
    )


def test_clean_hour_is_ok():
    report = validate(bars())
    assert report.status is QualityStatus.OK
    assert report.expected_bars == 60
    assert report.consumable is True


def test_internal_gap_degrades():
    series = bars()
    del series[30:32]  # two consecutive missing bars > tolerance 1
    report = validate(series)
    assert report.status is QualityStatus.DEGRADED
    assert report.gaps == 1
    assert report.gap_details[0][1] == 2


def test_non_monotonic_series_is_blocked():
    series = bars()
    series[10], series[11] = series[11], series[10]
    report = validate(series)
    assert report.status is QualityStatus.BLOCKED
    assert "non_monotonic_time" in report.reasons[0]


def test_invalid_ohlc_is_rejected_per_bar():
    series = bars()
    series[5] = MarketBar(
        symbol="XAUUSD.", timeframe=Timeframe.M1, time_utc=series[5].time_utc,
        open=4000, high=3990, low=3995, close=4001,
    )
    assert check_bar(series[5]) == "high_below_low"
    report = validate(series)
    assert report.invalid_bars == 1
    assert report.status is QualityStatus.DEGRADED


def test_zero_and_nan_prices_are_invalid():
    bad = MarketBar(symbol="XAUUSD.", timeframe=Timeframe.M1, time_utc=START,
                    open=0, high=0, low=0, close=0)
    assert check_bar(bad) == "non_positive_price"
    nan = MarketBar(symbol="XAUUSD.", timeframe=Timeframe.M1, time_utc=START,
                    open=float("nan"), high=1, low=1, close=1)
    assert check_bar(nan) == "non_finite_price"


def test_duplicate_bar_is_counted_and_degraded():
    series = bars()
    series.insert(10, series[9])
    report = validate(series)
    assert report.duplicates == 1
    assert report.status is QualityStatus.DEGRADED


def test_sparse_daily_series_is_quarantined():
    daily = []
    for day in range(30):
        t = START + timedelta(days=day)
        daily.append(
            MarketBar(symbol="XAUUSD.", timeframe=Timeframe.M1, time_utc=t,
                      open=4000, high=4001, low=3999, close=4000)
        )
    report = validate(daily)
    assert report.status is QualityStatus.BLOCKED
    assert "DAILY_RESOLUTION_DETECTED" in report.reasons[0]


def test_stale_tail_degrades_when_market_is_open():
    series = bars()
    now = series[-1].time_utc + timedelta(minutes=30)
    assert CAL.is_open(now) is True
    report = validate(series, now=now)
    assert report.status is QualityStatus.DEGRADED
    assert "STALE_FEED" in report.reasons


def test_empty_series_fails():
    report = validate_bars([], calendar=CAL, now_utc=START)
    assert report.status is QualityStatus.FAILED


def test_crossed_quote_is_rejected():
    tick = MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1_800_000_000_000,
                      bid=4001.0, ask=4000.0)
    assert check_tick(tick) == "crossed_quote"


def test_normal_tick_is_accepted():
    tick = MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1_800_000_000_000,
                      bid=4000.0, ask=4000.2)
    assert check_tick(tick) is None


def test_tick_dedupe_uses_the_documented_key():
    a = MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1000, bid=1.0, ask=1.1)
    b = MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1000, bid=1.0, ask=1.1)
    c = MarketTick(symbol="XAUUSD.", time_utc=START, time_msc=1000, bid=1.0, ask=1.2)
    assert len(dedupe_ticks([a, b, c])) == 2


def test_hole_across_a_closure_is_not_a_gap():
    """Audit F2: a run must not merge bars either side of a market closure."""
    friday = bars(120, start=datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc))  # 15:00–17:00 ET
    sunday = bars(60, start=datetime(2026, 11, 8, 23, 0, tzinfo=timezone.utc))  # 18:00 ET open
    report = validate(
        friday + sunday,
        now=datetime(2026, 11, 9, 0, 1, tzinfo=timezone.utc),
    )
    assert report.gaps == 0
    assert report.status is QualityStatus.OK


def test_daily_break_is_not_reported_as_a_gap():
    """MD-30: 17:00–18:00 ET halt must not look like missing data."""
    morning = bars(480, start=datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc))
    evening = bars(180, start=datetime(2026, 11, 4, 23, 0, tzinfo=timezone.utc))
    series = morning + evening
    report = validate(series, now=datetime(2026, 11, 5, 2, 1, tzinfo=timezone.utc))

    assert CAL.is_break(datetime(2026, 11, 4, 22, 30, tzinfo=timezone.utc)) is True
    assert report.gaps == 0
    assert report.status is QualityStatus.OK
    assert report.expected_bars == 660
