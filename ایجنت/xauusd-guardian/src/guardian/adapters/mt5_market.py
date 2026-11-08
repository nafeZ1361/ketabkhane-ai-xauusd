"""Read-only MT5 market-data adapter.

Composes :class:`Mt5ReadOnlyAdapter` for the session/identity duties and adds
``copy_rates_*`` / ``copy_ticks_*``. numpy structured arrays are converted to
frozen dataclasses here, so nothing downstream depends on numpy (D-004).

Never imports or calls ``order_send``/``order_check``.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from typing import Any

from guardian.adapters.mt5_readonly import Mt5ReadOnlyAdapter
from guardian.contracts.market import MarketBar, MarketTick, Timeframe
from guardian.contracts.schemas import SymbolSpec
from guardian.domain.market.broker_clock import BrokerClock

_TF_ATTR = {
    Timeframe.M1: "TIMEFRAME_M1",
    Timeframe.M5: "TIMEFRAME_M5",
    Timeframe.M15: "TIMEFRAME_M15",
    Timeframe.H1: "TIMEFRAME_H1",
    Timeframe.H4: "TIMEFRAME_H4",
}


def tick_age_seconds(tick_time_s: int, now_s: int, model_offset_s: int) -> int:
    """Signed age of a **server-time** tick relative to modelled server-now.

    ``tick.time`` runs ahead of UTC by the model offset, so raw UTC ``now``
    cannot be used directly. The sign carries the direction:

    * ``age > 0`` — the tick is **older** than server-now by that many seconds
      (ordinary transport latency, or a quiet symbol);
    * ``age == 0`` — the tick is stamped exactly at modelled server-now;
    * ``age < 0`` — the tick is stamped **ahead** of modelled server-now, i.e.
      the broker clock leads the model (live probes measured ~1.5 s).

    A lead is not an error: both directions are normal inside a few seconds,
    so freshness is a two-sided tolerance (see :func:`is_fresh_tick`).
    """
    return (int(now_s) + int(model_offset_s)) - int(tick_time_s)


MAX_TICK_AGE_S = 5


def is_fresh_tick(tick_time_s: int, now_s: int, model_offset_s: int, max_age_s: int = MAX_TICK_AGE_S) -> bool:
    """True when the tick is within ``max_age_s`` of server-now, either side.

    A non-positive broker timestamp is invalid and never fresh. The bound is
    symmetric: a tick 1 s old and a tick 1 s ahead are both usable, while a
    stale or far-future tick is refused.
    """
    if int(tick_time_s) <= 0:
        return False
    return abs(tick_age_seconds(tick_time_s, now_s, model_offset_s)) <= max_age_s


class Mt5MarketAdapter:
    def __init__(
        self,
        base: Mt5ReadOnlyAdapter | None = None,
        *,
        clock: BrokerClock | None = None,
    ) -> None:
        self._base = base or Mt5ReadOnlyAdapter()
        self._mt5: Any | None = None
        self._clock = clock or BrokerClock()

    # -- lifecycle (delegated to the approved read-only adapter) -----------
    def attach(self) -> dict[str, Any]:
        fingerprint = self._base.attach()
        self._mt5 = importlib.import_module("MetaTrader5")
        return fingerprint

    def detach(self) -> None:
        self._mt5 = None
        self._base.detach()

    def __enter__(self) -> "Mt5MarketAdapter":
        self.attach()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.detach()

    # -- identity ----------------------------------------------------------
    def account_identity(self) -> dict[str, str]:
        return self._base.account_identity()

    def symbol_specs(self) -> list[SymbolSpec]:
        return self._base.symbol_specs()

    def symbol_spec(self, name: str) -> SymbolSpec | None:
        return self._base.symbol_spec(name)

    def symbol_spread_points(self, name: str) -> int | None:
        return self._base.symbol_spread_points(name)

    # -- data --------------------------------------------------------------
    # -- single shared clock conversion -----------------------------------
    def to_utc(self, server_epoch_s: float) -> datetime:
        """Server wall-clock epoch → UTC through the one authoritative clock.

        ``BrokerClock`` resolves the DST offset per timestamp, so history that
        straddles a switch is not shifted by a constant. A measured offset is
        evidence only and must never drive conversion.
        """
        return self._clock.to_utc(server_epoch_s)

    def _require(self) -> Any:
        if self._mt5 is None:
            raise MarketDataError("adapter is not attached")
        return self._mt5

    # -- broker clock ------------------------------------------------------
    @property
    def server_offset_s(self) -> int:
        """Model offset in force right now, in seconds.

        This is the only conversion authority; the measured offset is not an
        input here (A6).
        """
        from datetime import datetime as _dt

        return self._clock.offset_for(_dt.now(timezone.utc))

    @property
    def broker_clock(self) -> BrokerClock:
        return self._clock

    def set_broker_clock(self, clock: BrokerClock) -> None:
        self._clock = clock

    def estimate_server_offset(
        self, symbol: str, samples: int = 10, pause_s: float = 0.05
    ) -> tuple[int, int, int] | None:
        """Measure the broker clock offset from live tick timestamps.

        Returns ``(offset_seconds, mad_seconds, sample_count)``. MT5 reports bar
        and tick times in **server** time, not UTC; the median is rounded to whole
        minutes so bar boundaries stay aligned.
        """
        import statistics
        import time as _time

        mt5 = self._require()
        from datetime import datetime as _dt

        model = self._clock.offset_for(_dt.now(timezone.utc))
        deltas: list[int] = []
        for _ in range(max(3, samples)):
            tick = mt5.symbol_info_tick(symbol)
            now = int(_time.time())
            if tick is not None and is_fresh_tick(int(tick.time), now, model):
                # tick.time is server time; compare it with server-local now
                deltas.append(int(tick.time) - now)
            _time.sleep(pause_s)
        if len(deltas) < 3:
            return None
        median = statistics.median(deltas)
        mad = statistics.median([abs(value - median) for value in deltas])
        rounded = int(round(median / 60.0) * 60)
        return rounded, int(mad), len(deltas)

    def rates(self, symbol: str, timeframe: Timeframe, count: int) -> list[MarketBar] | None:
        """Return the most recent ``count`` bars, or ``None`` on API failure."""
        mt5 = self._require()
        raw = mt5.copy_rates_from_pos(symbol, getattr(mt5, _TF_ATTR[timeframe]), 0, int(count))
        if raw is None:
            return None
        return [
            MarketBar(
                symbol=symbol,
                timeframe=timeframe,
                time_utc=self.to_utc(float(row["time"])),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                tick_volume=int(row["tick_volume"]),
                spread_points=int(row["spread"]),
                real_volume=float(row["real_volume"]),
            )
            for row in raw
        ]

    def ticks(
        self,
        symbol: str,
        start_utc: datetime,
        limit: int,
        end_utc: datetime | None = None,
    ) -> list[MarketTick] | None:
        """Ticks in ``[start_utc, end_utc]``.

        The terminal reads the request as a **server wall-clock** instant and
        applies its own offset to reach UTC, so the integer passed here is
        ``utc_epoch + model_offset``. A naive datetime is resolved through the
        host timezone first and the terminal then subtracts its own offset, so
        the previous form requested the window **4 h early** on this host
        (measured 2026-11-05: 2 h host zone + 2 h server offset). Returned ticks
        are still filtered against ``start_utc`` in UTC.
        """
        mt5 = self._require()
        start_utc = start_utc.astimezone(timezone.utc)
        request_s = int(start_utc.timestamp()) + self._clock.offset_for(start_utc)
        raw = mt5.copy_ticks_from(symbol, request_s, int(limit), mt5.COPY_TICKS_ALL)
        if raw is None:
            return None
        out: list[MarketTick] = []
        for row in raw:
            msc = int(row["time_msc"])
            tick_utc = self.to_utc(msc / 1000.0)
            if tick_utc < start_utc:
                continue
            if end_utc is not None and tick_utc > end_utc.astimezone(timezone.utc):
                continue
            out.append(
                MarketTick(
                    symbol=symbol,
                    time_utc=tick_utc,
                    time_msc=msc,
                    bid=float(row["bid"]),
                    ask=float(row["ask"]),
                    last=float(row["last"]),
                    volume=int(row["volume"]),
                    flags=int(row["flags"]),
                )
            )
        return out

    def quote(self, symbol: str) -> tuple[int, float, float] | None:
        mt5 = self._require()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        return int(tick.time_msc), float(tick.bid), float(tick.ask)
