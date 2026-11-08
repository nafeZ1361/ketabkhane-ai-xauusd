"""Server-offset estimation (median + MAD) for the three-clock model.

Input is a list of ``(tick_time_ms, received_utc)`` samples. A stale, duplicated
or future-dated sample is excluded before the median is taken; the estimator
returns ``UNKNOWN`` rather than a number when the evidence is insufficient.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Iterable, Sequence

from guardian.contracts.market import TimeSyncResult

MIN_SAMPLES = 10
MAD_LIMIT_MS = 2000.0
MAX_AGE_S = 5.0


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def estimate_offset(
    samples: Iterable[tuple[int, datetime]],
    *,
    max_age_s: float = MAX_AGE_S,
    min_samples: int = MIN_SAMPLES,
    mad_limit_ms: float = MAD_LIMIT_MS,
) -> TimeSyncResult:
    valid: list[float] = []
    seen_times: set[int] = set()

    for tick_ms, received in samples:
        if received.tzinfo is None:
            continue
        received_ms = _ms(received.astimezone(timezone.utc))
        age_ms = received_ms - tick_ms
        if tick_ms <= 0 or age_ms < 0 or age_ms > max_age_s * 1000:
            continue  # future-dated, stale, or impossible
        if tick_ms in seen_times:
            continue  # duplicate broker timestamp
        seen_times.add(tick_ms)
        valid.append(float(tick_ms - received_ms))

    if len(valid) < min_samples:
        return TimeSyncResult(
            status="UNKNOWN",
            samples=len(valid),
            reason=f"insufficient_samples:{len(valid)}<{min_samples}",
        )

    median = statistics.median(valid)
    mad = statistics.median([abs(value - median) for value in valid])
    status = "HIGH" if mad <= mad_limit_ms else "LOW"
    reason = "" if status == "HIGH" else f"MAD>{mad_limit_ms:.0f}ms:{mad:.0f}"

    return TimeSyncResult(
        status=status,
        offset_ms=median,
        mad_ms=mad,
        samples=len(valid),
        reason=reason,
    )
