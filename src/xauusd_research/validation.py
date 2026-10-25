"""Data quality checks for loaded candles (streaming and list API)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

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


class StreamingValidator:
    """Constant-memory validator: feed candles one by one, then call report()."""

    def __init__(self, gap_factor=1.5):
        self.gap_factor = gap_factor
        self.rows = 0
        self.issues = []
        self.deltas = Counter()
        self._prev = None

    def feed(self, candle):
        row = self.rows
        self.rows += 1
        prices = (candle.open, candle.high, candle.low, candle.close)
        if any(p <= 0 for p in prices):
            self.issues.append(Issue("NON_POSITIVE_PRICE", "price <= 0", row))
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close) or candle.high < candle.low:
            self.issues.append(Issue("BAD_OHLC", "inconsistent OHLC", row))
        prev = self._prev
        if prev is not None:
            delta = (candle.time - prev.time).total_seconds()
            if delta == 0:
                self.issues.append(Issue("DUPLICATE_TIME", "duplicate timestamp", row))
            elif delta < 0:
                self.issues.append(Issue("OUT_OF_ORDER", "timestamp goes backwards", row))
            else:
                self.deltas[int(delta)] += 1
        self._prev = candle

    def _median_delta(self):
        if not self.deltas:
            return 0
        items = sorted(self.deltas.items())
        total = sum(self.deltas.values())
        half = total / 2
        seen = 0
        for delta, count in items:
            seen += count
            if seen >= half:
                return delta
        return items[-1][0]

    def report(self):
        report = ValidationReport(rows=self.rows, issues=list(self.issues))
        if self.rows == 0:
            report.issues.append(Issue("EMPTY", "no data rows"))
            return report
        typical = self._median_delta()
        if typical > 0:
            report.gaps = sum(count for delta, count in self.deltas.items()
                              if delta > self.gap_factor * typical)
        return report


def validate(candles, gap_factor=1.5):
    validator = StreamingValidator(gap_factor)
    for candle in candles:
        validator.feed(candle)
    return validator.report()