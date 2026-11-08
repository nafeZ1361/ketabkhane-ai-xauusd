"""Market-data contracts (schema_version 2, same generation as the rest).

Raw broker values are carried without judgement: validation belongs to
``domain.market.quality``, so a bad bar can be *reported* instead of crashing
the collector at construction time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from guardian.contracts.schemas import SCHEMA_VERSION


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"

    @property
    def minutes(self) -> int:
        return {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}[self.value]


class QualityStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class FeedStatus(str, Enum):
    OK = "OK"
    STALE_FEED = "STALE_FEED"
    DEGRADED = "DEGRADED"
    DAILY_RESOLUTION_DETECTED = "DAILY_RESOLUTION_DETECTED"
    CALENDAR_DRIFT = "CALENDAR_DRIFT"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware (UTC)")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class MarketBar:
    symbol: str
    timeframe: Timeframe
    time_utc: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = 0
    spread_points: int = 0
    real_volume: float = 0.0
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        ensure_utc(self.time_utc)
        if not self.symbol:
            raise ValueError("symbol is required")

    @property
    def content_sha256(self) -> str:
        import hashlib

        raw = f"{self.open!r}|{self.high!r}|{self.low!r}|{self.close!r}|{self.tick_volume}"
        return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MarketTick:
    symbol: str
    time_utc: datetime
    time_msc: int
    bid: float
    ask: float
    last: float = 0.0
    volume: int = 0
    flags: int = 0
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        ensure_utc(self.time_utc)
        if self.time_msc <= 0:
            raise ValueError("time_msc must be positive")

    @property
    def spread_points(self) -> float:
        return self.ask - self.bid


@dataclass(frozen=True, slots=True)
class TimeSyncResult:
    status: str  # HIGH | LOW | UNKNOWN
    offset_ms: float | None = None
    mad_ms: float | None = None
    samples: int = 0
    reason: str = ""
    schema_version: int = SCHEMA_VERSION

    @property
    def confidence_high(self) -> bool:
        return self.status == "HIGH"

    @property
    def blocks_decisions(self) -> bool:
        return self.status != "HIGH"


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    symbol: str
    timeframe: Timeframe
    status: QualityStatus
    expected_bars: int = 0
    received_bars: int = 0
    duplicates: int = 0
    invalid_bars: int = 0
    gaps: int = 0
    max_gap_bars: int = 0
    gap_details: tuple[tuple[datetime, int], ...] = ()
    first_utc: datetime | None = None
    last_utc: datetime | None = None
    reasons: tuple[str, ...] = ()
    schema_version: int = SCHEMA_VERSION

    @property
    def consumable(self) -> bool:
        return self.status is QualityStatus.OK

    @property
    def summary(self) -> str:
        return (
            f"{self.symbol}/{self.timeframe.value}: {self.status.value} "
            f"rx={self.received_bars} exp={self.expected_bars} gaps={self.gaps} "
            f"invalid={self.invalid_bars} dup={self.duplicates}"
            + (f" | {'; '.join(self.reasons)}" if self.reasons else "")
        )


@dataclass(frozen=True, slots=True)
class FeedRun:
    run_id: str
    symbol: str
    kind: str  # bars | ticks
    timeframe: Timeframe | None = None
    started_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_utc: datetime | None = None
    status: str = "RUNNING"
    inserted: int = 0
    revised: int = 0
    gaps: int = 0
    reason: str = ""
    schema_version: int = SCHEMA_VERSION
