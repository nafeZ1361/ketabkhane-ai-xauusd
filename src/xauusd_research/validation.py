"""Data quality checks for loaded candles."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

FATAL_CODES = frozenset({"EMPTY", "DUPLICATE_TIME", "OUT_OF_ORDER", "BAD_OHLC", "NON_POSITIVE_PRICE"})


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    row: int | None = None


@dataclass
class ValidationReport:
    rows: int
    issues: list = field(default_factory=list)
    gaps: int = 0

    @property
    def fatal(self):
        return any(issue.code in FATAL_CODES for issue in self.issues)

    def codes(self):
        return sorted({issue.code for issue in self.issues})


def validate(candles, gap_factor=1.5):
    report = ValidationReport(rows=len(candles))
    if not candles:
        report.issues.append(Issue("EMPTY", "no data rows"))
        return report
    for row, candle in enumerate(candles):
        prices = (candle.open, candle.high, candle.low, candle.close)
        if any(p <= 0 for p in prices):
            report.issues.append(Issue("NON_POSITIVE_PRICE", "price <= 0", row))
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close) or candle.high < candle.low:
            report.issues.append(Issue("BAD_OHLC", "inconsistent OHLC", row))
    for row in range(1, len(candles)):
        prev, cur = candles[row - 1], candles[row]
        if cur.time == prev.time:
            report.issues.append(Issue("DUPLICATE_TIME", "duplicate timestamp", row))
        elif cur.time < prev.time:
            report.issues.append(Issue("OUT_OF_ORDER", "timestamp goes backwards", row))
    deltas = [(candles[i].time - candles[i - 1].time).total_seconds() for i in range(1, len(candles))]
    if deltas:
        typical = median(deltas)
        if typical > 0:
            report.gaps = sum(1 for d in deltas if d > gap_factor * typical)
    return report