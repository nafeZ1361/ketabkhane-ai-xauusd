"""Deterministic signal generation over stored bars (Phase 3, S5).

The service is a thin application layer: it decides *which* bars may be read,
delegates the strategy itself to :func:`guardian.domain.strategy.ema_cross.evaluate`,
and persists the result.

Rules enforced here (not by the strategy):

* only closed bars are read — a stored forming bar is skipped, never evaluated
  and never silently trimmed into a "closed" bar;
* bars belonging to a quarantined feed run are excluded from every read;
* the run window and ``run_id`` are derived from the bars alone, so a re-run at
  a different wall-clock time over the same closed bars is byte-identical;
* an existing stored signal that disagrees with a recomputation fails closed
  instead of being overwritten.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from guardian.contracts.market import MarketBar, Timeframe
from guardian.contracts.signals import Signal, SignalError, SignalRun, StrategySpec
from guardian.domain.strategy import ema_cross

#: Same predicate as ``guardian.storage.market_store._QUARANTINED_RUNS``.
#: Duplicated here on purpose: the service owns its own read and must not
#: depend on a private constant of the storage layer.
QUARANTINED_RUN_PREDICATE = "SELECT run_id FROM feed_runs WHERE status = 'QUARANTINED'"

DEFAULT_SYMBOL = "XAUUSD."
SUPPORTED_TIMEFRAME = Timeframe.M5


@dataclass(frozen=True, slots=True)
class SignalOutcome:
    """What one service call did, in enough detail to be evidence."""

    run: SignalRun
    signals: tuple[Signal, ...]
    written: int
    identical: int
    created: bool
    bars_digest: str


def _bars_digest(bars: list[MarketBar]) -> str:
    """Stable digest of the exact bars used, independent of ``now``."""
    digest = hashlib.sha256()
    for bar in bars:
        digest.update(
            f"{bar.time_utc.isoformat()}|{bar.open!r}|{bar.high!r}|{bar.low!r}|"
            f"{bar.close!r}|{bar.tick_volume}|{bar.spread_points}|{bar.real_volume!r}\n".encode()
        )
    return digest.hexdigest()


class SignalService:
    """Generate and persist ``ema_cross_v1`` signals for one symbol."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        symbol: str = DEFAULT_SYMBOL,
        timeframe: Timeframe = SUPPORTED_TIMEFRAME,
        spec: StrategySpec = ema_cross.SPEC,
    ) -> None:
        if not isinstance(symbol, str) or not symbol.strip():
            raise SignalError("symbol is required")
        if timeframe is not SUPPORTED_TIMEFRAME:
            raise SignalError(f"unsupported timeframe: {getattr(timeframe, 'value', timeframe)!r}")
        if spec.id != ema_cross.SPEC.id:
            raise SignalError(f"unknown strategy: {spec.id!r}")
        self._conn = conn
        self._symbol = symbol
        self._timeframe = timeframe
        self._spec = spec

    # -- input validation ---------------------------------------------------
    @staticmethod
    def _require_aware(now: datetime) -> datetime:
        """Normalise ``now`` to UTC, refusing any unusable offset.

        The same three failure modes W1 closed in ``ema_cross`` are checked
        here, because this is the entry point the CLI uses.
        """
        if not isinstance(now, datetime):
            raise SignalError("now must be a datetime")
        if now.tzinfo is None:
            raise SignalError("now must be timezone-aware")
        try:
            offset = now.utcoffset()
        except (TypeError, ValueError, OverflowError) as exc:
            raise SignalError("now must have a valid UTC offset") from exc
        if offset is None:
            raise SignalError("now must have a valid UTC offset")
        return now.astimezone(timezone.utc)

    # -- reads --------------------------------------------------------------
    def load_closed_bars(self, now: datetime) -> list[MarketBar]:
        """Closed, non-quarantined bars for this symbol/timeframe, ascending."""
        moment = self._require_aware(now)
        minutes = self._timeframe.minutes
        rows = self._conn.execute(
            "SELECT symbol, time_utc, open, high, low, close, tick_volume, spread_points, real_volume "
            "FROM bars "
            "WHERE symbol = ? AND timeframe = ? "
            f"AND run_id NOT IN ({QUARANTINED_RUN_PREDICATE}) "
            "ORDER BY time_utc",
            (self._symbol, self._timeframe.value),
        ).fetchall()

        bars: list[MarketBar] = []
        for row in rows:
            recorded = datetime.fromisoformat(row["time_utc"])
            if recorded.tzinfo is None or recorded.utcoffset() is None:
                # Fail closed: never guess that a naive timestamp is UTC.
                raise SignalError(f"stored bar time is not timezone-aware: {row['time_utc']!r}")
            bar_time = recorded.astimezone(timezone.utc)
            if bar_time + timedelta(minutes=minutes) > moment:
                continue  # still forming: excluded, not fabricated
            bars.append(
                MarketBar(
                    symbol=row["symbol"],
                    timeframe=self._timeframe,
                    time_utc=bar_time,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    tick_volume=row["tick_volume"],
                    spread_points=row["spread_points"],
                    real_volume=row["real_volume"],
                )
            )
        return bars

    # -- identity -----------------------------------------------------------
    def _build_run_id(self, bars: list[MarketBar], from_utc: datetime, to_utc: datetime) -> str:
        material = "|".join(
            [
                self._spec.id,
                self._spec.version,
                self._timeframe.value,
                self._symbol,
                from_utc.isoformat(),
                to_utc.isoformat(),
                str(len(bars)),
                _bars_digest(bars),
            ]
        )
        return "run_" + hashlib.sha256(material.encode()).hexdigest()[:24]

    # -- write --------------------------------------------------------------
    def _existing_signal(self, signal: Signal) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT direction, strength, reason_code FROM signals "
            "WHERE symbol = ? AND timeframe = ? AND bar_time_utc = ? AND strategy_id = ?",
            (signal.symbol, signal.timeframe, signal.bar_time_utc.isoformat(), signal.strategy_id),
        ).fetchone()

    def run(self, *, now: datetime) -> SignalOutcome:
        """Evaluate closed bars and persist the result in one transaction."""
        moment = self._require_aware(now)
        bars = self.load_closed_bars(moment)
        if not bars:
            raise SignalError("no closed bars available")
        if len(bars) < self._spec.warmup_bars:
            raise SignalError(
                f"insufficient closed bars: need {self._spec.warmup_bars}, got {len(bars)}"
            )

        signals = ema_cross.evaluate(bars, strategy_id=self._spec.id, now=moment)
        from_utc = bars[0].time_utc
        to_utc = bars[-1].time_utc + timedelta(minutes=self._timeframe.minutes)
        run_id = self._build_run_id(bars, from_utc, to_utc)
        digest = _bars_digest(bars)
        created_at = datetime.now(timezone.utc).isoformat()

        already = self._conn.execute(
            "SELECT run_id FROM signal_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        created = already is None
        written = 0
        identical = 0

        with self._conn:  # commit on success, rollback on any exception
            if created:
                self._conn.execute(
                    "INSERT INTO signal_runs (run_id, symbol, strategy_id, timeframe, from_utc, to_utc, "
                    "bars_seen, signals, written, identical, status, created_utc) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        self._symbol,
                        self._spec.id,
                        self._timeframe.value,
                        from_utc.isoformat(),
                        to_utc.isoformat(),
                        len(bars),
                        len(signals),
                        0,
                        0,
                        "OK",
                        created_at,
                    ),
                )
            for signal in signals:
                existing = self._existing_signal(signal)
                if existing is None:
                    self._conn.execute(
                        "INSERT INTO signals (symbol, timeframe, bar_time_utc, strategy_id, direction, "
                        "strength, reason_code, run_id, created_utc) VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            signal.symbol,
                            signal.timeframe,
                            signal.bar_time_utc.isoformat(),
                            signal.strategy_id,
                            signal.direction.value,
                            str(signal.strength),
                            signal.reason_code,
                            run_id,
                            created_at,
                        ),
                    )
                    written += 1
                elif (
                    str(existing["direction"]),
                    str(existing["reason_code"]),
                    Decimal(existing["strength"]),
                ) == (signal.direction.value, signal.reason_code, signal.strength):
                    identical += 1
                else:
                    # A revised bar changed an already-published signal. That is a
                    # human decision, not something this service may overwrite.
                    raise SignalError(
                        f"stored signal conflicts with recomputation at "
                        f"{signal.bar_time_utc.isoformat()}"
                    )
            if created:
                self._conn.execute(
                    "UPDATE signal_runs SET written = ?, identical = ? WHERE run_id = ?",
                    (written, identical, run_id),
                )

        run = SignalRun(
            run_id=run_id,
            strategy_id=self._spec.id,
            timeframe=self._timeframe.value,
            from_utc=from_utc,
            to_utc=to_utc,
            bars_seen=len(bars),
            signals=len(signals),
            status="OK",
        )
        return SignalOutcome(
            run=run,
            signals=tuple(signals),
            written=written,
            identical=identical,
            created=created,
            bars_digest=digest,
        )
