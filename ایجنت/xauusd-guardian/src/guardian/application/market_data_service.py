"""Market-data collection orchestration.

Owns the attach → verify → collect → validate → persist → detach lifecycle.
Every outcome is a value; the CLI decides the exit code.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from guardian.application.symbol_service import check_account_identity
from guardian.contracts.market import FeedRun, QualityStatus, Timeframe
from guardian.domain.market.quality import check_bar, check_tick, dedupe_ticks, validate_bars
from guardian.domain.market.session import SessionCalendar
from guardian.domain.symbols import GoldExpectations, identify_gold_symbol
from guardian.storage.market_store import MarketStore, QuotaExceeded

BYTES_PER_TICK_ESTIMATE = 130


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class MarketRunConfig:
    policy: str = "xauusd_identity_v3"
    expectations: GoldExpectations = field(default_factory=GoldExpectations)
    expected_server: str = "AronMarkets-Demo"
    expected_currency: str = "USD"
    expected_trade_mode: str = "DEMO"
    expected_company: str | None = None
    gap_tolerance_bars: int = 1
    stale_after_bars: int = 2
    min_bars_ratio: float = 0.5
    max_tick_window_h: int = 6
    tick_limit: int = 200_000


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    status: str
    runs: tuple[FeedRun, ...] = ()
    reasons: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def _aggregate(statuses: Sequence[str]) -> str:
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "FAILED" in statuses:
        return "FAILED"
    if "DEGRADED" in statuses:
        return "DEGRADED"
    return "OK"


class MarketDataService:
    def __init__(
        self,
        adapter: Any,
        store: MarketStore,
        calendar: SessionCalendar,
        config: MarketRunConfig | None = None,
        *,
        clock: Any = _now,
    ) -> None:
        self._adapter = adapter
        self._store = store
        self._calendar = calendar
        self._config = config or MarketRunConfig()
        self._clock = clock
        self._clock_note: str | None = None

    # -- shared guard ------------------------------------------------------
    def _apply_clock(self, symbol: str) -> str | None:
        """Pin and cross-check the broker clock before any timestamp is trusted.

        With no fresh ticks (quiet market or daily halt) the deterministic model
        is still used — timestamps stay correct — but the run is marked
        DEGRADED via ``self._clock_note``, never silently accepted.
        """
        self._clock_note = None
        measured = self._adapter.estimate_server_offset(symbol)
        if measured is None:
            self._clock_note = "clock_unverified:no_fresh_ticks"
            return None
        offset, mad, samples = measured
        clock = self._adapter.broker_clock
        now = self._clock()
        if not clock.matches(offset, now):
            return (
                f"server offset {offset}s does not match the modelled broker clock "
                f"({clock.offset_for(now)}s); refusing to timestamp bars"
            )
        if mad > 2:
            self._store.record_time_sync("LOW", float(offset) * 1000.0, float(mad) * 1000.0, samples)
            return f"server clock unstable (MAD {mad}s > 2s); refusing to timestamp bars"
        # The measured offset is evidence, never a conversion input: the DST
        # model stays the single authoritative clock (A6).
        self._store.record_time_sync("HIGH", float(offset) * 1000.0, float(mad) * 1000.0, samples)
        return None

    def _guard(self) -> tuple[str | None, str | None]:
        """Return ``(symbol, problem)`` — exactly one is non-None."""
        identity = self._adapter.account_identity()
        problem = check_account_identity(
            identity,
            expected_trade_mode=self._config.expected_trade_mode,
            expected_server=self._config.expected_server,
            expected_currency=self._config.expected_currency,
            expected_company=self._config.expected_company,
        )
        if problem:
            return None, problem

        resolution = identify_gold_symbol(
            self._adapter.symbol_specs(),
            policy=self._config.policy,
            account_currency=self._config.expected_currency,
            expectations=self._config.expectations,
        )
        if not resolution.ok:
            return None, f"symbol {resolution.status.value}: {resolution.reason}"
        return resolution.symbol_name, None

    # -- bars --------------------------------------------------------------
    def collect_bars(self, timeframes: Sequence[Timeframe], count: int) -> CollectionOutcome:
        if count <= 0:
            raise ValueError("count must be positive")
        try:
            self._adapter.attach()
        except Exception as exc:
            return CollectionOutcome("CONNECTION_FAILED", (), (f"terminal attach failed: {exc}",))

        try:
            symbol, problem = self._guard()
            if problem:
                return CollectionOutcome("BLOCKED", (), (problem,))
            clock_problem = self._apply_clock(symbol)
            if clock_problem:
                return CollectionOutcome("BLOCKED", (), (clock_problem,))
            runs = tuple(self._collect_one(symbol, tf, count) for tf in timeframes)
        finally:
            self._adapter.detach()

        return CollectionOutcome(_aggregate([r.status for r in runs]), runs)

    def _collect_one(self, symbol: str, timeframe: Timeframe, count: int) -> FeedRun:
        run_id = uuid.uuid4().hex
        run = FeedRun(run_id=run_id, symbol=symbol, kind="bars", timeframe=timeframe, started_utc=self._clock())
        self._store.record_run_start(run)

        bars = self._adapter.rates(symbol, timeframe, count)
        if bars is None:
            self._store.finish_run(run_id, status="FAILED", reason="copy_rates returned None")
            return replace(run, status="FAILED", reason="copy_rates returned None")
        if not bars:
            self._store.finish_run(run_id, status="FAILED", reason="empty_series")
            return replace(run, status="FAILED", reason="empty_series")

        report = validate_bars(
            bars,
            calendar=self._calendar,
            now_utc=self._clock(),
            gap_tolerance_bars=self._config.gap_tolerance_bars,
            stale_after_bars=self._config.stale_after_bars,
            min_bars_ratio=self._config.min_bars_ratio,
        )

        reasons = list(report.reasons)
        status = report.status
        if self._clock_note:
            reasons.append(self._clock_note)
            if status is QualityStatus.OK:
                status = QualityStatus.DEGRADED
        report = replace(report, status=status, reasons=tuple(reasons))

        if report.status is QualityStatus.BLOCKED:
            reason = "; ".join(report.reasons) or "blocked"
            self._store.quarantine(run_id, symbol, timeframe.value, reason)
            self._store.finish_run(run_id, status="BLOCKED", reason=reason)
            return replace(run, status="BLOCKED", reason=reason)

        clean = [bar for bar in bars if check_bar(bar) is None]
        result = self._store.upsert_bars(run_id, clean)
        if report.gap_details:
            self._store.record_gaps(run_id, symbol, timeframe.value, report.gap_details)

        self._store.finish_run(
            run_id,
            status=report.status.value,
            inserted=result.inserted,
            revised=result.revised,
            gaps=report.gaps,
            reason="; ".join(report.reasons),
        )
        return replace(
            run,
            status=report.status.value,
            inserted=result.inserted,
            revised=result.revised,
            gaps=report.gaps,
            reason="; ".join(report.reasons),
            finished_utc=self._clock(),
        )

    # -- ticks -------------------------------------------------------------
    def collect_ticks(self, start_utc: datetime, end_utc: datetime) -> CollectionOutcome:
        now = self._clock()
        if start_utc.tzinfo is None or end_utc.tzinfo is None:
            raise ValueError("window must be timezone-aware")
        window = end_utc - start_utc
        if window <= timedelta(0):
            return CollectionOutcome("FAILED", (), ("empty_window",))
        if window > timedelta(hours=self._config.max_tick_window_h):
            return CollectionOutcome(
                "BLOCKED", (), (f"window {window} exceeds max_tick_window_h={self._config.max_tick_window_h}",)
            )
        if end_utc > now + timedelta(minutes=1):
            return CollectionOutcome("BLOCKED", (), ("window ends in the future",))

        try:
            self._adapter.attach()
        except Exception as exc:
            return CollectionOutcome("CONNECTION_FAILED", (), (f"terminal attach failed: {exc}",))

        try:
            symbol, problem = self._guard()
            if problem:
                return CollectionOutcome("BLOCKED", (), (problem,))
            clock_problem = self._apply_clock(symbol)
            if clock_problem:
                return CollectionOutcome("BLOCKED", (), (clock_problem,))
            if self._clock_note:
                # F-C: ticks are millisecond evidence — never stored on an unverified clock
                return CollectionOutcome("BLOCKED", (), (self._clock_note,))

            run_id = uuid.uuid4().hex
            run = FeedRun(run_id=run_id, symbol=symbol, kind="ticks", started_utc=now)
            self._store.record_run_start(run)

            raw = self._adapter.ticks(symbol, start_utc, self._config.tick_limit, end_utc)
            if raw is None:
                self._store.finish_run(run_id, status="FAILED", reason="copy_ticks returned None")
                return CollectionOutcome("FAILED", (replace(run, status="FAILED"),), ("copy_ticks returned None",))

            ticks = dedupe_ticks(raw)
            crossed = sum(1 for tick in ticks if check_tick(tick) == "crossed_quote")
            clean = [tick for tick in ticks if check_tick(tick) is None]
            truncated = len(raw) >= self._config.tick_limit

            if not clean:
                # A5: an empty result is a failure, never a silent success
                reason = "empty_after_filter:no_ticks_in_window"
                self._store.finish_run(run_id, status="FAILED", reason=reason)
                return CollectionOutcome("FAILED", (replace(run, status="FAILED", reason=reason),), (reason,))

            projected = self._store.usage_bytes() + len(clean) * BYTES_PER_TICK_ESTIMATE
            if projected > self._store.quota_bytes:
                reason = f"quota_exceeded:need={projected}B quota={self._store.quota_bytes}B"
                self._store.finish_run(run_id, status="BLOCKED", reason=reason)
                return CollectionOutcome("BLOCKED", (replace(run, status="BLOCKED", reason=reason),), (reason,))

            try:
                inserted = self._store.insert_ticks(run_id, clean)
            except QuotaExceeded as exc:
                self._store.finish_run(run_id, status="BLOCKED", reason=str(exc))
                return CollectionOutcome("BLOCKED", (replace(run, status="BLOCKED", reason=str(exc)),), (str(exc),))

            status = "DEGRADED" if (crossed or truncated) else "OK"
            notes = []
            if crossed:
                notes.append(f"crossed_quotes:{crossed}")
            if truncated:
                notes.append("tick_window_truncated:limit_reached")
            reason = "; ".join(notes)
            self._store.finish_run(run_id, status=status, inserted=inserted, reason=reason)
            return CollectionOutcome(status, (replace(run, status=status, inserted=inserted, reason=reason),))
        finally:
            self._adapter.detach()
