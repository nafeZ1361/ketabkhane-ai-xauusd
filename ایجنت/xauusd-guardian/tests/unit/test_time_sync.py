"""Time-sync estimator: MD-13…MD-16, MD-31 (DST handled in session tests)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from guardian.domain.market.time_sync import estimate_offset

BASE = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)


def samples(n=12, offset_ms=-40, spread_ms=0):
    out = []
    for i in range(n):
        received = BASE + timedelta(seconds=i)
        jitter = spread_ms if i % 2 == 0 else -spread_ms
        tick_ms = int(received.timestamp() * 1000) + offset_ms + jitter
        out.append((tick_ms, received))
    return out


def test_clean_samples_give_high_confidence():
    result = estimate_offset(samples())
    assert result.status == "HIGH"
    assert result.samples == 12
    assert result.confidence_high is True
    assert abs(result.offset_ms - (-40)) <= 1


def test_large_mad_is_low_confidence():
    out = []
    for i in range(12):
        received = BASE + timedelta(seconds=i)
        skew = -50 if i % 2 == 0 else -4500  # 50 ms vs 4.5 s of latency noise
        out.append((int(received.timestamp() * 1000) + skew, received))
    result = estimate_offset(out)
    assert result.status == "LOW"
    assert result.blocks_decisions is True
    assert "MAD" in result.reason


def test_insufficient_samples_is_unknown():
    result = estimate_offset(samples(n=4))
    assert result.status == "UNKNOWN"
    assert result.offset_ms is None


def test_stale_samples_are_excluded():
    fresh = samples(n=10)
    stale = [(tick - 60_000, received) for tick, received in samples(n=5)]
    result = estimate_offset(fresh + stale)
    assert result.samples == 10


def test_duplicate_tick_times_are_excluded():
    base = samples(n=10)
    result = estimate_offset(base + base)
    assert result.samples == 10


def test_future_dated_sample_is_rejected():
    future = [(int((BASE + timedelta(minutes=5)).timestamp() * 1000), BASE)]
    result = estimate_offset(future + samples(n=10))
    assert result.samples == 10


def test_naive_datetime_is_ignored():
    naive = [(int(BASE.timestamp() * 1000), datetime(2026, 11, 4, 15, 0))]
    result = estimate_offset(naive + samples(n=10))
    assert result.samples == 10
