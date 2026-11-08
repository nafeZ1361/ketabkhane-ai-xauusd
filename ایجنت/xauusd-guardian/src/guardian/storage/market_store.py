"""SQLite persistence for market data.

Bars are append-only in effect: the current row is updated only after the prior
version is written to ``bar_revisions``, so a broker revision is recorded rather
than silently overwritten. Ticks dedupe on ``(symbol, time_msc, bid, ask)``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from guardian.contracts.market import FeedRun, MarketBar, MarketTick

BYTES_PER_TICK_ESTIMATE = 130
QUARANTINED = "QUARANTINED"

# Every read that returns market data must exclude runs a human quarantined.
# NOT IN (rather than IN live) keeps legacy rows whose run row is absent visible.
_QUARANTINED_RUNS = "SELECT run_id FROM feed_runs WHERE status = 'QUARANTINED'"


class QuotaExceeded(RuntimeError):
    """Raised when the next chunk would push storage past the configured quota."""


@dataclass(frozen=True, slots=True)
class UpsertResult:
    inserted: int = 0
    revised: int = 0
    unchanged: int = 0


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class MarketStore:
    def __init__(self, conn: sqlite3.Connection, *, quota_bytes: int) -> None:
        if quota_bytes <= 0:
            raise ValueError("quota_bytes must be positive")
        self._conn = conn
        self._quota = quota_bytes

    # -- accounting --------------------------------------------------------
    def _db_path(self) -> str:
        row = self._conn.execute("PRAGMA database_list").fetchone()
        return row["file"] if row else ""

    def usage_bytes(self) -> int:
        page_count = self._conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = self._conn.execute("PRAGMA page_size").fetchone()[0]
        total = int(page_count) * int(page_size)
        path = self._db_path()
        if path:
            for suffix in ("-wal", "-shm"):
                try:
                    total += os.path.getsize(path + suffix)
                except OSError:
                    pass
        return total

    @property
    def quota_bytes(self) -> int:
        return self._quota

    def _check_quota(self, extra_bytes: int) -> None:
        projected = self.usage_bytes() + max(0, extra_bytes)
        if projected > self._quota:
            raise QuotaExceeded(
                f"quota {self._quota} B would be exceeded: usage {self.usage_bytes()} B + {extra_bytes} B"
            )

    # -- runs --------------------------------------------------------------
    def record_run_start(self, run: FeedRun) -> None:
        self._conn.execute(
            "INSERT INTO feed_runs (run_id, symbol, kind, timeframe, started_utc, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run.run_id, run.symbol, run.kind, run.timeframe.value if run.timeframe else None,
             _iso(run.started_utc), "RUNNING"),
        )
        self._conn.commit()

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        inserted: int = 0,
        revised: int = 0,
        gaps: int = 0,
        reason: str = "",
    ) -> None:
        self._conn.execute(
            "UPDATE feed_runs SET finished_utc = ?, status = ?, inserted = ?, revised = ?, gaps = ?, reason = ? "
            "WHERE run_id = ?",
            (_iso(datetime.now(timezone.utc)), status, inserted, revised, gaps, reason, run_id),
        )
        self._conn.commit()

    # -- bars --------------------------------------------------------------
    def upsert_bars(self, run_id: str, bars: Sequence[MarketBar]) -> UpsertResult:
        inserted = revised = unchanged = 0
        now = _iso(datetime.now(timezone.utc))
        for bar in bars:
            row = self._conn.execute(
                "SELECT content_sha256 FROM bars WHERE symbol = ? AND timeframe = ? AND time_utc = ?",
                (bar.symbol, bar.timeframe.value, _iso(bar.time_utc)),
            ).fetchone()
            digest = bar.content_sha256
            if row is None:
                self._conn.execute(
                    "INSERT INTO bars (symbol, timeframe, time_utc, open, high, low, close, tick_volume, "
                    "spread_points, real_volume, content_sha256, first_seen_utc, last_seen_utc, run_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (bar.symbol, bar.timeframe.value, _iso(bar.time_utc), bar.open, bar.high, bar.low,
                     bar.close, bar.tick_volume, bar.spread_points, bar.real_volume, digest, now, now, run_id),
                )
                self._conn.execute(
                    "INSERT OR IGNORE INTO bar_revisions (symbol, timeframe, time_utc, seen_utc, open, high, low, "
                    "close, tick_volume, content_sha256, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (bar.symbol, bar.timeframe.value, _iso(bar.time_utc), now, bar.open, bar.high, bar.low,
                     bar.close, bar.tick_volume, digest, run_id),
                )
                inserted += 1
            elif row["content_sha256"] == digest:
                self._conn.execute(
                    "UPDATE bars SET last_seen_utc = ? WHERE symbol = ? AND timeframe = ? AND time_utc = ?",
                    (now, bar.symbol, bar.timeframe.value, _iso(bar.time_utc)),
                )
                unchanged += 1
            else:
                self._conn.execute(
                    "INSERT OR IGNORE INTO bar_revisions (symbol, timeframe, time_utc, seen_utc, open, high, low, "
                    "close, tick_volume, content_sha256, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (bar.symbol, bar.timeframe.value, _iso(bar.time_utc), now, bar.open, bar.high, bar.low,
                     bar.close, bar.tick_volume, digest, run_id),
                )
                self._conn.execute(
                    "UPDATE bars SET open=?, high=?, low=?, close=?, tick_volume=?, content_sha256=?, "
                    "last_seen_utc=?, run_id=? WHERE symbol=? AND timeframe=? AND time_utc=?",
                    (bar.open, bar.high, bar.low, bar.close, bar.tick_volume, digest, now, run_id,
                     bar.symbol, bar.timeframe.value, _iso(bar.time_utc)),
                )
                revised += 1
        self._conn.commit()
        return UpsertResult(inserted=inserted, revised=revised, unchanged=unchanged)

    # -- ticks -------------------------------------------------------------
    def insert_ticks(self, run_id: str, ticks: Iterable[MarketTick], *, chunk_size: int = 10_000) -> int:
        total = 0
        batch: list[tuple] = []
        for tick in ticks:
            batch.append(
                (tick.symbol, tick.time_msc, _iso(tick.time_utc), tick.bid, tick.ask, tick.last,
                 tick.volume, tick.flags, run_id)
            )
            if len(batch) >= chunk_size:
                total += self._flush_ticks(batch)
                batch = []
        if batch:
            total += self._flush_ticks(batch)
        return total

    def _flush_ticks(self, batch: list[tuple]) -> int:
        self._check_quota(len(batch) * BYTES_PER_TICK_ESTIMATE)
        before = self._conn.total_changes
        self._conn.executemany(
            "INSERT OR IGNORE INTO ticks (symbol, time_msc, time_utc, bid, ask, last, volume, flags, run_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            batch,
        )
        self._conn.commit()
        return self._conn.total_changes - before

    # -- gaps / quarantine -------------------------------------------------
    def record_gaps(
        self, run_id: str, symbol: str, timeframe: str, gaps: Sequence[tuple[datetime, int]]
    ) -> None:
        """``gaps`` is a sequence of ``(gap_start_utc, bars_missing)``."""
        if not gaps:
            return
        now = _iso(datetime.now(timezone.utc))
        self._conn.executemany(
            "INSERT INTO data_gaps (run_id, symbol, timeframe, gap_start_utc, bars_missing, created_utc) "
            "VALUES (?,?,?,?,?,?)",
            [(run_id, symbol, timeframe, _iso(start), missing, now) for start, missing in gaps],
        )
        self._conn.commit()

    def quarantine(self, run_id: str, symbol: str, timeframe: str, reason: str) -> None:
        """Series-level marker (sparse daily data). Not a run-level quarantine."""
        self._conn.execute(
            "INSERT INTO quarantined_series (run_id, symbol, timeframe, reason, created_utc) VALUES (?,?,?,?,?)",
            (run_id, symbol, timeframe, reason, _iso(datetime.now(timezone.utc))),
        )
        self._conn.commit()

    # -- run quarantine (reversible, enforced by every read) ---------------
    def quarantine_run(self, run_id: str, reason: str) -> str:
        """Mark ``run_id`` quarantined; return its previous status.

        The status is stored on the run row and the previous value is written to
        ``audit_events``, which makes :meth:`restore_run` exact rather than a
        guess. Tick runs have no timeframe, so the state lives on the run — not
        in ``quarantined_series``, whose ``timeframe`` is NOT NULL.
        """
        row = self._conn.execute("SELECT status FROM feed_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError(f"unknown run: {run_id}")
        previous = str(row["status"])
        if previous == QUARANTINED:
            return previous
        self._conn.execute(
            "INSERT INTO audit_events (created_utc, run_id, event_type, severity, message, payload) "
            "VALUES (?,?,?,?,?,?)",
            (
                _iso(datetime.now(timezone.utc)),
                run_id,
                "QUARANTINE_APPLIED",
                "WARNING",
                reason,
                json.dumps({"previous_status": previous}),
            ),
        )
        self._conn.execute("UPDATE feed_runs SET status = ? WHERE run_id = ?", (QUARANTINED, run_id))
        self._conn.commit()
        return previous

    def restore_run(self, run_id: str) -> str:
        """Undo :meth:`quarantine_run`; return the status now in force."""
        row = self._conn.execute("SELECT status FROM feed_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise ValueError(f"unknown run: {run_id}")
        if str(row["status"]) != QUARANTINED:
            return str(row["status"])
        event = self._conn.execute(
            "SELECT payload FROM audit_events WHERE run_id = ? AND event_type = 'QUARANTINE_APPLIED' "
            "ORDER BY id DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if event is None or not event["payload"]:
            raise ValueError(f"no quarantine record for run: {run_id}")
        previous = str(json.loads(event["payload"])["previous_status"])
        self._conn.execute("UPDATE feed_runs SET status = ? WHERE run_id = ?", (previous, run_id))
        self._conn.execute(
            "INSERT INTO audit_events (created_utc, run_id, event_type, severity, message, payload) "
            "VALUES (?,?,?,?,?,?)",
            (
                _iso(datetime.now(timezone.utc)),
                run_id,
                "QUARANTINE_LIFTED",
                "INFO",
                "restored by operator",
                json.dumps({"restored_status": previous}),
            ),
        )
        self._conn.commit()
        return previous

    def quarantined_runs(self) -> list[str]:
        return [
            str(row["run_id"])
            for row in self._conn.execute("SELECT run_id FROM feed_runs WHERE status = ?", (QUARANTINED,))
        ]

    def record_time_sync(self, status: str, offset_ms: float | None, mad_ms: float | None, samples: int) -> None:
        self._conn.execute(
            "INSERT INTO time_sync (created_utc, status, offset_ms, mad_ms, samples) VALUES (?,?,?,?,?)",
            (_iso(datetime.now(timezone.utc)), status, offset_ms, mad_ms, samples),
        )
        self._conn.commit()

    # -- health ------------------------------------------------------------
    def health(self) -> dict[str, object]:
        """Counts downstream code may trust: quarantined runs are excluded."""
        bars = self._conn.execute(f"SELECT COUNT(*) AS c FROM bars WHERE run_id NOT IN ({_QUARANTINED_RUNS})").fetchone()["c"]
        ticks = self._conn.execute(f"SELECT COUNT(*) AS c FROM ticks WHERE run_id NOT IN ({_QUARANTINED_RUNS})").fetchone()["c"]
        revisions = self._conn.execute(
            f"SELECT COUNT(*) AS c FROM bar_revisions WHERE run_id NOT IN ({_QUARANTINED_RUNS})"
        ).fetchone()["c"]
        runs = self._conn.execute("SELECT COUNT(*) AS c FROM feed_runs").fetchone()["c"]
        quarantined = self._conn.execute(
            "SELECT COUNT(*) AS c FROM feed_runs WHERE status = 'QUARANTINED'"
        ).fetchone()["c"]
        return {
            "bars": bars,
            "bar_revisions": revisions,
            "ticks": ticks,
            "runs": runs,
            "quarantined_runs": quarantined,
            "usage_bytes": self.usage_bytes(),
            "quota_bytes": self._quota,
        }

    def last_bar(self, symbol: str, timeframe: str) -> dict[str, object] | None:
        row = self._conn.execute(
            f"SELECT time_utc, close FROM bars WHERE symbol = ? AND timeframe = ? "
            f"AND run_id NOT IN ({_QUARANTINED_RUNS}) ORDER BY time_utc DESC LIMIT 1",
            (symbol, timeframe),
        ).fetchone()
        return dict(row) if row else None
