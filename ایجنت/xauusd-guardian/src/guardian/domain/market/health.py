"""Pure feed-health alert rules; no MT5 calls or network I/O."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class HealthLimits:
    max_tick_age_seconds: Decimal
    max_spread_points: Decimal
    max_spread_multiple: Decimal

    def __post_init__(self) -> None:
        for name in ("max_tick_age_seconds", "max_spread_points", "max_spread_multiple"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} must be a positive finite Decimal")


@dataclass(frozen=True, slots=True)
class FeedHealthSnapshot:
    connected: bool
    tick_age_seconds: Decimal | None
    spread_points: Decimal | None
    baseline_spread_points: Decimal | None


@dataclass(frozen=True, slots=True)
class HealthReport:
    status: HealthStatus
    alerts: tuple[str, ...]


def evaluate_feed_health(snapshot: FeedHealthSnapshot, limits: HealthLimits) -> HealthReport:
    if not isinstance(snapshot, FeedHealthSnapshot) or not isinstance(limits, HealthLimits):
        raise ValueError("snapshot and limits must use declared contracts")
    alerts: list[str] = []
    if not isinstance(snapshot.connected, bool):
        alerts.append("CONNECTION_STATE_INVALID")
    elif not snapshot.connected:
        alerts.append("CONNECTION_LOST")
    if snapshot.tick_age_seconds is None:
        alerts.append("TICK_MISSING")
    elif (not isinstance(snapshot.tick_age_seconds, Decimal)
          or not snapshot.tick_age_seconds.is_finite() or snapshot.tick_age_seconds < 0):
        alerts.append("TICK_AGE_INVALID")
    elif snapshot.tick_age_seconds > limits.max_tick_age_seconds:
        alerts.append("TICK_STALE")
    if snapshot.spread_points is None or snapshot.baseline_spread_points is None:
        alerts.append("SPREAD_UNKNOWN")
    elif (
        not isinstance(snapshot.spread_points, Decimal)
        or not isinstance(snapshot.baseline_spread_points, Decimal)
        or not snapshot.spread_points.is_finite()
        or not snapshot.baseline_spread_points.is_finite()
        or snapshot.spread_points < 0
        or snapshot.baseline_spread_points <= 0
    ):
        alerts.append("SPREAD_INVALID")
    else:
        if snapshot.spread_points > limits.max_spread_points:
            alerts.append("SPREAD_ABSOLUTE_LIMIT")
        if snapshot.spread_points > snapshot.baseline_spread_points * limits.max_spread_multiple:
            alerts.append("SPREAD_ANOMALY")
    blocking = {"CONNECTION_LOST", "CONNECTION_STATE_INVALID", "TICK_MISSING", "TICK_AGE_INVALID", "TICK_STALE", "SPREAD_UNKNOWN", "SPREAD_INVALID"}
    if any(item in blocking for item in alerts):
        status = HealthStatus.BLOCKED
    elif alerts:
        status = HealthStatus.DEGRADED
    else:
        status = HealthStatus.HEALTHY
    return HealthReport(status=status, alerts=tuple(alerts))
