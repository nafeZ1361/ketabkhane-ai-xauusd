"""Event-driven OHLC backtest with explicit spread, slippage and commission.

Signals are formed at a bar close and can execute only at the next bar open.
If stop and target both trade inside one OHLC bar, the stop is assumed first.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from guardian.contracts.market import MarketBar
from guardian.contracts.signals import Direction, Signal


class BacktestError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionCostModel:
    point_size: Decimal
    value_per_point_lot: Decimal
    slippage_points_per_side: Decimal = Decimal("0")
    commission_per_lot_per_side: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name in ("point_size", "value_per_point_lot", "slippage_points_per_side", "commission_per_lot_per_side"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise BacktestError(f"{name} must be a finite Decimal")
        if self.point_size <= 0 or self.value_per_point_lot <= 0:
            raise BacktestError("point_size and value_per_point_lot must be positive")
        if self.slippage_points_per_side < 0 or self.commission_per_lot_per_side < 0:
            raise BacktestError("costs cannot be negative")


@dataclass(frozen=True, slots=True)
class Trade:
    direction: Direction
    entry_time_utc: object
    exit_time_utc: object
    entry_price: Decimal
    exit_price: Decimal
    lots: Decimal
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal
    exit_reason: str


@dataclass(frozen=True, slots=True)
class BacktestResult:
    trades: tuple[Trade, ...]
    initial_equity: Decimal
    final_equity: Decimal
    total_net_pnl: Decimal
    max_drawdown: Decimal


@dataclass(slots=True)
class _Position:
    direction: Direction
    entry_time: object
    entry_price: Decimal
    lots: Decimal
    stop: Decimal | None
    target: Decimal | None


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def run_backtest(
    bars: Sequence[MarketBar],
    signals: Sequence[Signal],
    *,
    lots: Decimal,
    initial_equity: Decimal,
    costs: ExecutionCostModel,
    stop_loss_points: Decimal | None = None,
    take_profit_points: Decimal | None = None,
) -> BacktestResult:
    if len(bars) < 2:
        raise BacktestError("at least two bars are required")
    for name, value in (("lots", lots), ("initial_equity", initial_equity)):
        if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
            raise BacktestError(f"{name} must be a positive finite Decimal")
    for name, value in (("stop_loss_points", stop_loss_points), ("take_profit_points", take_profit_points)):
        if value is not None and (not isinstance(value, Decimal) or not value.is_finite() or value <= 0):
            raise BacktestError(f"{name} must be a positive finite Decimal")
    if any(bars[i].time_utc >= bars[i + 1].time_utc for i in range(len(bars) - 1)):
        raise BacktestError("bars must be strictly increasing")
    if any(bars[i].symbol != bars[0].symbol or bars[i].timeframe != bars[0].timeframe for i in range(len(bars))):
        raise BacktestError("bars must share symbol and timeframe")
    index = {bar.time_utc: i for i, bar in enumerate(bars)}
    scheduled: dict[int, Signal] = {}
    for signal in signals:
        if signal.bar_time_utc not in index:
            raise BacktestError("signal timestamp does not match a supplied bar")
        i = index[signal.bar_time_utc]
        if i >= len(bars) - 1:
            raise BacktestError("last-bar signal cannot execute without a next bar")
        if i in scheduled:
            raise BacktestError("multiple signals on one bar are ambiguous")
        if signal.direction not in (Direction.LONG, Direction.SHORT, Direction.FLAT):
            raise BacktestError("unsupported signal direction")
        scheduled[i] = signal

    position: _Position | None = None
    trades: list[Trade] = []
    equity = initial_equity
    peak = initial_equity
    max_dd = Decimal(0)

    def close_position(bar: MarketBar, raw_price: Decimal, reason: str) -> None:
        nonlocal position, equity, peak, max_dd
        assert position is not None
        spread_cost = _d(bar.spread_points) / Decimal(2)
        slip = costs.slippage_points_per_side
        adjustment = (spread_cost + slip) * costs.point_size
        exit_price = raw_price - adjustment if position.direction is Direction.LONG else raw_price + adjustment
        signed_points = (
            (exit_price - position.entry_price) / costs.point_size
            if position.direction is Direction.LONG
            else (position.entry_price - exit_price) / costs.point_size
        )
        gross = signed_points * costs.value_per_point_lot * position.lots
        commission = costs.commission_per_lot_per_side * position.lots * Decimal(2)
        net = gross - commission
        trades.append(Trade(position.direction, position.entry_time, bar.time_utc, position.entry_price,
                            exit_price, position.lots, gross, commission, net, reason))
        equity += net
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        position = None

    for i in range(1, len(bars)):
        bar = bars[i]
        prior_signal = scheduled.get(i - 1)
        if position is not None and prior_signal is not None:
            if prior_signal.direction is Direction.FLAT or prior_signal.direction is not position.direction:
                close_position(bar, _d(bar.open), "OPPOSITE_OR_FLAT_SIGNAL")
        if position is None and prior_signal is not None and prior_signal.direction in (Direction.LONG, Direction.SHORT):
            half_spread = _d(bar.spread_points) / Decimal(2)
            entry_adjustment = (half_spread + costs.slippage_points_per_side) * costs.point_size
            entry = _d(bar.open) + entry_adjustment if prior_signal.direction is Direction.LONG else _d(bar.open) - entry_adjustment
            stop = None
            target = None
            if stop_loss_points is not None:
                stop = entry - stop_loss_points * costs.point_size if prior_signal.direction is Direction.LONG else entry + stop_loss_points * costs.point_size
            if take_profit_points is not None:
                target = entry + take_profit_points * costs.point_size if prior_signal.direction is Direction.LONG else entry - take_profit_points * costs.point_size
            position = _Position(prior_signal.direction, bar.time_utc, entry, lots, stop, target)

        if position is not None:
            high, low, open_price = _d(bar.high), _d(bar.low), _d(bar.open)
            if position.direction is Direction.LONG:
                stop_hit = position.stop is not None and low <= position.stop
                target_hit = position.target is not None and high >= position.target
                if stop_hit:
                    close_position(bar, min(open_price, position.stop), "STOP_LOSS")
                elif target_hit:
                    close_position(bar, max(open_price, position.target), "TAKE_PROFIT")
            else:
                stop_hit = position.stop is not None and high >= position.stop
                target_hit = position.target is not None and low <= position.target
                if stop_hit:
                    close_position(bar, max(open_price, position.stop), "STOP_LOSS")
                elif target_hit:
                    close_position(bar, min(open_price, position.target), "TAKE_PROFIT")

    if position is not None:
        last = bars[-1]
        close_position(last, _d(last.close), "END_OF_DATA")
    total = equity - initial_equity
    return BacktestResult(tuple(trades), initial_equity, equity, total, max_dd)
