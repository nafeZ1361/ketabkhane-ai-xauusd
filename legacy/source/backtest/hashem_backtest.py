import numpy as np
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import threading
import warnings
import time
import re
import os
import MetaTrader5 as mt5
warnings.filterwarnings('ignore')


DAY_SECONDS = 86400
DAY_MS = DAY_SECONDS * 1000
_TF_UNITS = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
_FALLBACK_PIP_VALUES = {'XAUUSD': 10.0, 'EURUSD': 10.0, 'GBPUSD': 10.0, 'USDJPY': 9.0}
_EMPTY_DAYS_LIMIT = 10


def timeframe_seconds(timeframe):
    match = re.fullmatch(r'(\d+)([mhdw])', str(timeframe).strip())
    if not match or int(match.group(1)) == 0:
        raise ValueError(f"Timeframe {timeframe} not supported. Use: ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']")
    return int(match.group(1)) * _TF_UNITS[match.group(2)]


def _bucket(seconds, tf):
    if tf % _TF_UNITS['w'] == 0:
        span = tf // DAY_SECONDS
        return ((seconds // DAY_SECONDS + 4) // span * span - 4) * DAY_SECONDS
    return seconds // tf * tf


def _ohlc(keys, o, h, l, c, v):
    if len(keys) == 0:
        return keys, o, h, l, c, v
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]])
    ends = np.r_[starts[1:], len(keys)] - 1
    return (keys[starts], o[starts], np.maximum.reduceat(h, starts),
            np.minimum.reduceat(l, starts), c[ends], np.add.reduceat(v, starts))


def _heikin_ashi(o, h, l, c):
    ha_close = (o + h + l + c) / 4
    ha_open = np.empty_like(ha_close)
    if len(ha_close):
        closes = ha_close.tolist()
        opens = [0.0] * len(closes)
        prev = opens[0] = float(o[0])
        for i in range(1, len(closes)):
            prev = (prev + closes[i - 1]) / 2
            opens[i] = prev
        ha_open[:] = opens
    return (ha_open, np.maximum(np.maximum(ha_open, ha_close), h),
            np.minimum(np.minimum(ha_open, ha_close), l), ha_close)


def _copy_ticks(symbol, start, end):
    weekend = (start // DAY_SECONDS + 3) % 7 >= 5
    ticks = None
    for attempt in range(3):
        ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_ALL)
        if ticks is None:
            time.sleep(0.2)
        elif len(ticks) or weekend or attempt:
            break
    if ticks is None or len(ticks) == 0:
        return None
    t, bid, ask = ticks['time_msc'], ticks['bid'], ticks['ask']
    mask = (t >= start * 1000) & (t < end * 1000) & (bid > 0) & (ask > 0)
    if not mask.any():
        return None
    return t[mask].astype(np.int64), bid[mask].astype(np.float64), ask[mask].astype(np.float64)


def _fetch_ticks(symbol, start, end, empty_days=0, last_tick=0):
    parts = []
    day_end = end
    while day_end > start and empty_days < _EMPTY_DAYS_LIMIT:
        day = max(start, (day_end - 1) // DAY_SECONDS * DAY_SECONDS)
        part = _copy_ticks(symbol, day, day_end)
        if part is None:
            if day < last_tick:
                empty_days += 1
        else:
            parts.append(part)
            empty_days = 0
        day_end = day
    if not parts:
        return np.empty(0, np.int64), np.empty(0), np.empty(0), day_end, empty_days
    parts.reverse()
    t, bid, ask = (np.concatenate([p[i] for p in parts]) for i in range(3))
    if len(t) > 1 and (t[1:] < t[:-1]).any():
        order = np.argsort(t, kind='stable')
        t, bid, ask = t[order], bid[order], ask[order]
    return t, bid, ask, day_end, empty_days


class _TickStore:
    def __init__(self, symbol):
        self.symbol = symbol
        self.lock = threading.RLock()
        self.t = np.empty(0, np.int64)
        self.bid = np.empty(0)
        self.ask = np.empty(0)
        self.m1 = (np.empty(0, np.int64),) + tuple(np.empty(0) for _ in range(4)) + (np.empty(0, np.int64),)
        self.start = None
        self.anchor = None
        self.last_tick = 0
        self.empty_days = 0
        self.frames = {}

    @property
    def exhausted(self):
        return self.empty_days >= _EMPTY_DAYS_LIMIT

    def _anchor(self):
        if self.anchor is None:
            mt5.initialize()
            mt5.symbol_select(self.symbol, True)
            tick = mt5.symbol_info_tick(self.symbol)
            now = int(time.time()) + DAY_SECONDS
            self.last_tick = int(tick.time_msc) // 1000 if tick is not None and tick.time_msc > 0 else now
            self.anchor = max(self.last_tick + 1, now)
        return self.anchor

    def _extend(self, days):
        end = self.start if self.start is not None else self._anchor()
        start = (end // DAY_SECONDS - days) * DAY_SECONDS
        t, bid, ask, self.start, self.empty_days = _fetch_ticks(self.symbol, start, end, self.empty_days, self.last_tick)
        if len(t):
            m1 = _ohlc(t // 60000 * 60, bid, bid, bid, bid, np.ones(len(t), np.int64))
            self.m1 = tuple(np.concatenate([new, old]) for new, old in zip(m1, self.m1))
            self.t = np.concatenate([t, self.t])
            self.bid = np.concatenate([bid, self.bid])
            self.ask = np.concatenate([ask, self.ask])
            self.frames.clear()

    def _frame(self, tf, heikin_ashi):
        frame = self.frames.get((tf, heikin_ashi))
        if frame is None:
            if heikin_ashi:
                times, o, h, l, c, v = self._frame(tf, False)
                frame = (times,) + _heikin_ashi(o, h, l, c) + (v,)
            else:
                keys, o, h, l, c, v = self.m1 if tf == 60 else _ohlc(_bucket(self.m1[0], tf), *self.m1[1:])
                frame = (pd.to_datetime(keys, unit='s').to_numpy(), o, h, l, c, v)
            self.frames[(tf, heikin_ashi)] = frame
        return frame

    def candles(self, tf, limit, heikin_ashi):
        with self.lock:
            while True:
                count = len(self._frame(tf, False)[0])
                if count >= limit or self.exhausted:
                    break
                self._extend(max(2, int(np.ceil((limit - count) * tf * 1.5 / DAY_SECONDS)) + 1))
            times, o, h, l, c, v = self._frame(tf, heikin_ashi)
        s = max(0, len(times) - limit)
        return pd.DataFrame({'time': times[s:], 'open': o[s:], 'high': h[s:], 'low': l[s:], 'close': c[s:], 'volume': v[s:]})

    def ticks(self, start_ms, end_ms):
        with self.lock:
            while not self.exhausted and (self.start is None or self.start * 1000 > start_ms):
                ref = self.start if self.start is not None else self._anchor()
                self._extend(max(1, -(-(ref * 1000 - start_ms) // DAY_MS)))
            t, bid, ask = self.t, self.bid, self.ask
        i0, i1 = np.searchsorted(t, [start_ms, end_ms])
        return t[i0:i1], bid[i0:i1], ask[i0:i1]


_STORES = {}
_SPECS = {}
_CONTEXTS = {}
_STORES_LOCK = threading.Lock()


def _store(symbol):
    with _STORES_LOCK:
        store = _STORES.get(symbol)
        if store is None:
            store = _STORES[symbol] = _TickStore(symbol)
        return store


def reset_tick_data(symbol=None):
    with _STORES_LOCK:
        for cache in (_STORES, _SPECS):
            if symbol is None:
                cache.clear()
            else:
                cache.pop(symbol, None)
        for key in [k for k in _CONTEXTS if symbol is None or k[0] == symbol]:
            _CONTEXTS.pop(key, None)


def _symbol_specs(symbol):
    specs = _SPECS.get(symbol)
    if specs is not None:
        return specs
    mt5.initialize()
    info = mt5.symbol_info(symbol)
    digits = info.digits if info is not None else 5
    pip = (10 ** -digits) * 10
    try:
        if info is None:
            raise ValueError(f"Symbol {symbol} not found")
        value = (pip / info.trade_tick_size) * info.trade_tick_value
        currency = info.currency_profit
        if currency != "USD":
            if mt5.symbol_info(currency + "USD"):
                value *= mt5.symbol_info_tick(currency + "USD").bid
            elif mt5.symbol_info("USD" + currency):
                value /= mt5.symbol_info_tick("USD" + currency).bid
            else:
                raise RuntimeError(f"Cannot find USD conversion rate for {currency}")
    except Exception:
        value = _FALLBACK_PIP_VALUES.get(symbol, 10.0)
    specs = _SPECS[symbol] = (pip, value)
    return specs


class _Context:
    __slots__ = ('bar_open', 'bar_tick', 't', 'bid', 'ask', 'pip', 'pip_value')


def _context(df, symbol, tf):
    bar_open = pd.to_datetime(df['time']).to_numpy().astype('datetime64[ms]').astype(np.int64)
    key = (symbol, tf, len(bar_open), int(bar_open[0]), int(bar_open[-1]))
    ctx = _CONTEXTS.get(key)
    if ctx is not None:
        return ctx
    try:
        tf_ms = timeframe_seconds(tf) * 1000
    except ValueError:
        steps = np.diff(bar_open)
        steps = steps[steps > 0]
        tf_ms = int(steps.min()) if len(steps) else 60000
    bar_close = bar_open + tf_ms
    t, bid, ask = _store(symbol).ticks(int(bar_open[0]), int(bar_close[-1]))
    bar_tick = np.searchsorted(t, bar_close)
    if len(t):
        bar_tick[bar_close <= t[0]] = len(t)
    ctx = _Context()
    ctx.bar_open, ctx.bar_tick, ctx.t, ctx.bid, ctx.ask = bar_open, bar_tick, t, bid, ask
    ctx.pip, ctx.pip_value = _symbol_specs(symbol)
    if len(_CONTEXTS) >= 16:
        _CONTEXTS.clear()
    _CONTEXTS[key] = ctx
    return ctx


def _first_hit(prices, start, stop, low, high):
    size = 1024
    while start < stop:
        end = min(stop, start + size)
        chunk = prices[start:end]
        if low == -np.inf:
            hits = chunk >= high
        elif high == np.inf:
            hits = chunk <= low
        else:
            hits = (chunk <= low) | (chunk >= high)
        i = int(hits.argmax())
        if hits[i]:
            return start + i
        start = end
        size = min(size * 4, 1 << 20)
    return -1


def _simulate(ctx, trigger_signals, confirmation_signals, use_risk_free, risk_free_distance_pips,
              use_sl, sl_pips, use_tp, tp_pips, close_opposite_position, initial_balance,
              position_size_mode, fixed_lot_size, risk_percent, risk_based_on, daily=False):
    t, bid, ask, pip, pip_value = ctx.t, ctx.bid, ctx.ask, ctx.pip, ctx.pip_value
    n_ticks = len(t)
    trigger = np.asarray(trigger_signals, dtype=object)
    confirmation = np.asarray(confirmation_signals, dtype=object)
    direction = (((trigger == 'buy') & (confirmation == 'buy')).astype(np.int8)
                 - ((trigger == 'sell') & (confirmation == 'sell')).astype(np.int8))
    bars = np.flatnonzero(direction)
    event_ticks = ctx.bar_tick[bars]
    valid = event_ticks < n_ticks
    bars, event_ticks = bars[valid], event_ticks[valid]
    if len(event_ticks) > 1:
        last = np.r_[event_ticks[1:] != event_ticks[:-1], True]
        bars, event_ticks = bars[last], event_ticks[last]
    sides = direction[bars]
    buy_events = np.flatnonzero(sides > 0)
    sell_events = np.flatnonzero(sides < 0)

    pip_value_lot = round(pip_value, 3)
    sizing_sl = sl_pips if use_sl else 50

    def lot_size(balance):
        if position_size_mode == 'risk_percent':
            risk_balance = initial_balance if risk_based_on == 'initial' else balance
            if sizing_sl > 0 and pip_value_lot > 0:
                return max(0.01, round(risk_balance * (risk_percent / 100) / (sizing_sl * pip_value_lot), 2))
        return fixed_lot_size

    inf = np.inf
    sl_distance = sl_pips * pip
    tp_distance = tp_pips * pip
    rf_distance = risk_free_distance_pips * pip
    balance = peak = initial_balance
    max_dd = max_dd_pct = realized_dd = 0.0
    max_daily_dd = max_daily_dd_pct = 0.0
    day_start = {}
    trades = []
    event = 0
    n_events = len(event_ticks)

    while event < n_events:
        entry_tick = int(event_ticks[event])
        side = int(sides[event])
        lot = lot_size(balance)
        value = round(pip_value * lot, 3)
        prices = bid if side > 0 else ask
        entry = float(ask[entry_tick] if side > 0 else bid[entry_tick])
        sl = entry - side * sl_distance if use_sl else None
        tp = entry + side * tp_distance if use_tp else None
        rf = entry + side * rf_distance if use_risk_free else None

        stop, bound = n_ticks, -1
        if close_opposite_position:
            opposite = sell_events if side > 0 else buy_events
            q = int(np.searchsorted(opposite, event, 'right'))
            if q < len(opposite):
                bound = int(event_ticks[opposite[q]])
                stop = bound + 1

        exit_tick, reason, exit_price, rf_active = -1, None, None, False
        cursor = entry_tick + 1
        while True:
            pending_rf = rf if rf is not None and not rf_active else None
            if side > 0:
                low = -inf if sl is None else sl
                high = min(inf if tp is None else tp, inf if pending_rf is None else pending_rf)
            else:
                low = max(-inf if tp is None else tp, -inf if pending_rf is None else pending_rf)
                high = inf if sl is None else sl
            if low == -inf and high == inf:
                break
            hit = _first_hit(prices, cursor, stop, low, high)
            if hit < 0:
                break
            price = float(prices[hit])
            if tp is not None and (price >= tp if side > 0 else price <= tp):
                exit_tick, reason, exit_price = hit, 'TP', tp
                break
            if sl is not None and (price <= sl if side > 0 else price >= sl):
                exit_tick, reason, exit_price = hit, 'SL', price
                break
            sl, rf_active, cursor = entry, True, hit + 1

        if exit_tick < 0:
            if bound < 0:
                break
            exit_tick, reason, exit_price = bound, 'Manual Close', float(prices[bound])

        profit = side * (exit_price - entry) / pip * value
        segment = prices[entry_tick:exit_tick + 1]
        worst = float(segment.min() if side > 0 else segment.max())
        worst_equity = balance + side * (worst - entry) / pip * value
        if peak - worst_equity > max_dd:
            max_dd = peak - worst_equity
            max_dd_pct = max_dd / peak * 100 if peak > 0 else 0

        if daily:
            first_day = int(t[entry_tick] // DAY_MS)
            last_day = int(t[exit_tick] // DAY_MS)
            for day in range(first_day, last_day + 1):
                if first_day == last_day:
                    day_worst = worst_equity
                else:
                    a = max(entry_tick, int(np.searchsorted(t, day * DAY_MS)))
                    b = min(exit_tick + 1, int(np.searchsorted(t, (day + 1) * DAY_MS)))
                    if a >= b:
                        continue
                    part = prices[a:b]
                    day_worst = balance + side * (float(part.min() if side > 0 else part.max()) - entry) / pip * value
                start_balance = day_start.setdefault(day, balance)
                if start_balance - day_worst > max_daily_dd:
                    max_daily_dd = start_balance - day_worst
                    max_daily_dd_pct = max_daily_dd / start_balance * 100 if start_balance > 0 else 0

        balance += profit
        if balance > peak:
            peak = balance
        if peak - balance > max_dd:
            max_dd = peak - balance
            max_dd_pct = max_dd / peak * 100 if peak > 0 else 0
        realized_dd = max(realized_dd, peak - balance)
        trades.append((side, entry_tick, exit_tick, entry, exit_price, reason, profit, lot, value, rf_active, sl, tp))
        event = int(np.searchsorted(event_ticks, exit_tick))

    return {
        'trades': trades,
        'balance': balance,
        'peak_balance': peak,
        'max_drawdown': max_dd,
        'max_drawdown_percent': max_dd_pct,
        'realized_max_drawdown': realized_dd,
        'max_daily_drawdown': max_daily_dd,
        'max_daily_drawdown_percent': max_daily_dd_pct,
    }


def _positions(ctx, trades):
    if not trades:
        return []
    entry_ms = ctx.t[[tr[1] for tr in trades]]
    exit_ms = ctx.t[[tr[2] for tr in trades]]
    entry_index = np.searchsorted(ctx.bar_open, entry_ms, 'right') - 1
    exit_index = np.searchsorted(ctx.bar_open, exit_ms, 'right') - 1
    entry_time = pd.to_datetime(entry_ms, unit='ms')
    exit_time = pd.to_datetime(exit_ms, unit='ms')
    return [{
        'type': 'buy' if tr[0] > 0 else 'sell',
        'entry_index': int(entry_index[i]),
        'entry_time': entry_time[i],
        'entry_price': tr[3],
        'risk_free_activated': tr[9],
        'sl_price': tr[10],
        'tp_price': tr[11],
        'lot_size': tr[7],
        'pip_value_usd': tr[8],
        'exit_index': int(exit_index[i]),
        'exit_time': exit_time[i],
        'exit_price': tr[4],
        'exit_reason': tr[5],
        'profit_usd': tr[6],
    } for i, tr in enumerate(trades)]


def backtest(df, trigger_signals, confirmation_signals, symbol, tf,
             backtest_days, use_risk_free, risk_free_distance_pips,
             use_sl, sl_pips, use_tp, tp_pips,
             close_opposite_position, initial_balance,
             position_size_mode, fixed_lot_size,
             risk_percent, risk_based_on,
             analyze_weekdays, analyze_time_sessions,
             session_duration_hours):

    if len(df) != len(trigger_signals) or len(df) != len(confirmation_signals):
        raise ValueError(f"Length of dataframe and signal lists must match df : {len(df)}, trigger_signals : {len(trigger_signals)}, confirmation_signals : {len(confirmation_signals)}")

    ctx = _context(df, symbol, tf) if len(df) else None
    result = _simulate(ctx, trigger_signals, confirmation_signals, use_risk_free, risk_free_distance_pips,
                       use_sl, sl_pips, use_tp, tp_pips, close_opposite_position, initial_balance,
                       position_size_mode, fixed_lot_size, risk_percent, risk_based_on, daily=True) if ctx else None
    positions = _positions(ctx, result['trades']) if result else []

    if len(positions) == 0:
        print("No trades executed")
        return None

    for p in positions:
        if p['exit_reason'] == 'Manual Close' and p['profit_usd'] < 0:
            p['exit_reason'] = 'SL'

    max_drawdown = result['max_drawdown']
    max_drawdown_percent = result['max_drawdown_percent']
    max_daily_drawdown = result['max_daily_drawdown']
    max_daily_drawdown_percent = result['max_daily_drawdown_percent']

    balance = initial_balance
    balance_history = [initial_balance]
    balance_times = [df.iloc[0]['time']]
    for p in positions:
        balance += p['profit_usd']
        balance_history.append(balance)
        balance_times.append(p['exit_time'])

    total_trades = len(positions)
    print(f"\n{'='*80}")
    print(f"BACKTEST COMPLETED - TRADE STATISTICS")
    print(f"{'='*80}")
    print(f"Total Trades Executed: {total_trades}")

    winning_trades = [p for p in positions if p['profit_usd'] > 0]
    losing_trades = [p for p in positions if p['profit_usd'] < 0]
    breakeven_trades = [p for p in positions if p['profit_usd'] == 0]

    total_profit_usd = sum(p['profit_usd'] for p in positions)
    final_balance = initial_balance + total_profit_usd

    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

    print(f"Winning Trades: {len(winning_trades)}")
    print(f"Losing Trades: {len(losing_trades)}")
    print(f"Breakeven Trades: {len(breakeven_trades)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total Profit: ${total_profit_usd:.2f}")
    print(f"Final Balance: ${final_balance:.2f}")
    print(f"ROI: {((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0:.2f}%")
    print(f"{'='*80}\n")

    non_breakeven_count = total_trades - len(breakeven_trades)
    win_rate_no_breakeven = (len(winning_trades) / non_breakeven_count * 100) if non_breakeven_count > 0 else 0

    gross_profit_usd = sum(p['profit_usd'] for p in winning_trades) if winning_trades else 0
    gross_loss_usd = abs(sum(p['profit_usd'] for p in losing_trades)) if losing_trades else 0

    avg_win_usd = (gross_profit_usd / len(winning_trades)) if winning_trades else 0
    avg_loss_usd = (gross_loss_usd / len(losing_trades)) if losing_trades else 0

    roi = ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0

    profit_factor_usd = (gross_profit_usd / gross_loss_usd) if gross_loss_usd > 0 else float('inf')

    avg_lot_size = sum(p['lot_size'] for p in positions) / len(positions)

    returns = np.array([p['profit_usd'] for p in positions])
    avg_return = returns.mean()
    std_return = returns.std() if len(returns) > 1 else 0
    sharpe_ratio = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0

    weekday_analysis = None
    if analyze_weekdays:
        weekday_profits = {d: 0 for d in range(7)}
        weekday_counts = {d: 0 for d in range(7)}
        for p in positions:
            weekday = p['entry_time'].weekday()
            weekday_profits[weekday] += p['profit_usd']
            weekday_counts[weekday] += 1
        weekday_analysis = {
            'profits': weekday_profits,
            'counts': weekday_counts
        }

    time_session_analysis = None
    if analyze_time_sessions and session_duration_hours >= 0.5:
        session_duration_minutes = int(session_duration_hours * 60)
        entry_minutes = np.array([p['entry_time'].hour * 60 + p['entry_time'].minute for p in positions])

        start_times = []
        for hour in range(24):
            start_times.append(hour * 60)
            if hour < 23 or session_duration_minutes <= 30:
                start_times.append(hour * 60 + 30)

        session_profits = {}
        for start_min in start_times:
            end_min = start_min + session_duration_minutes
            if end_min > 24 * 60:
                continue
            mask = (entry_minutes >= start_min) & (entry_minutes < end_min)
            session_key = f"{start_min // 60:02d}:{start_min % 60:02d}-{end_min // 60:02d}:{end_min % 60:02d}"
            session_profits[session_key] = {
                'profit': float(returns[mask].sum()),
                'count': int(mask.sum())
            }

        best_session = max(session_profits.items(), key=lambda x: x[1]['profit']) if session_profits else None
        worst_session = min(session_profits.items(), key=lambda x: x[1]['profit']) if session_profits else None

        time_session_analysis = {
            'all_sessions': session_profits,
            'best_session': best_session,
            'worst_session': worst_session
        }

    fig_price = go.Figure()

    fig_price.add_trace(go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    ))

    markers = [
        ([p for p in positions if p['type'] == 'buy'], 'entry',
         dict(symbol='triangle-up', size=15, color='lime', line=dict(width=2, color='darkgreen')), 'Buy Entry', 'Buy Entry'),
        ([p for p in positions if p['type'] == 'sell'], 'entry',
         dict(symbol='triangle-down', size=15, color='red', line=dict(width=2, color='darkred')), 'Sell Entry', 'Sell Entry'),
        ([p for p in positions if p['exit_reason'] == 'TP'], 'exit',
         dict(symbol='star', size=12, color='gold', line=dict(width=1, color='orange')), 'Take Profit', 'TP Exit'),
        ([p for p in positions if p['exit_reason'] == 'SL' and p['profit_usd'] < 0], 'exit',
         dict(symbol='x', size=12, color='purple', line=dict(width=2)), 'Stop Loss', 'SL Exit'),
        ([p for p in positions if p['exit_reason'] == 'Manual Close'], 'exit',
         dict(symbol='circle-open', size=12, color='orange', line=dict(width=2)), 'Manual Close', 'Manual Close'),
    ]
    for group, side, marker, name, label in markers:
        if group:
            fig_price.add_trace(go.Scatter(
                x=[p[f'{side}_time'] for p in group],
                y=[p[f'{side}_price'] for p in group],
                mode='markers',
                marker=marker,
                name=name,
                hovertemplate=f'{label}<br>Price: %{{y:.5f}}<extra></extra>'
            ))

    fig_price.update_layout(
        title=f'{symbol} {tf} Price Chart',
        xaxis_title='Time',
        yaxis_title='Price',
        template='plotly_dark',
        height=600,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )

    fig_balance = go.Figure()

    fig_balance.add_trace(go.Scatter(
        x=balance_times,
        y=balance_history,
        mode='lines',
        name='Balance',
        line=dict(color='cyan', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 255, 0.1)',
        hovertemplate='Balance: $%{y:.2f}<extra></extra>'
    ))

    fig_balance.update_layout(
        title='Balance Curve',
        xaxis_title='Time',
        yaxis_title='Balance ($)',
        template='plotly_dark',
        height=400,
        hovermode='x unified'
    )

    fig_weekday_html = ""
    if weekday_analysis:
        fig_weekday = go.Figure()

        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_profits_list = [weekday_analysis['profits'][i] for i in range(7)]
        weekday_colors = ['green' if p > 0 else 'red' for p in weekday_profits_list]

        fig_weekday.add_trace(go.Bar(
            x=weekday_names,
            y=weekday_profits_list,
            name='Profit by Day',
            marker=dict(color=weekday_colors),
            text=[f'${p:.2f}' for p in weekday_profits_list],
            textposition='outside',
            hovertemplate='%{x}<br>Profit: $%{y:.2f}<extra></extra>'
        ))

        fig_weekday.update_layout(
            title='Profit by Weekday',
            xaxis_title='Day of Week',
            yaxis_title='Profit ($)',
            template='plotly_dark',
            height=400,
            showlegend=False
        )

        fig_weekday_html = fig_weekday.to_html(include_plotlyjs=False, div_id='weekday_chart')

    fig_time_session_html = ""
    time_session_table_html = ""
    if time_session_analysis:
        sessions_data = time_session_analysis['all_sessions']

        sessions_with_trades = {k: v for k, v in sessions_data.items() if v['count'] > 0}

        if sessions_with_trades:
            sorted_sessions = sorted(sessions_with_trades.items(), key=lambda x: x[1]['profit'], reverse=True)

            top_sessions = sorted_sessions[:10]
            session_names = [s[0] for s in top_sessions]
            session_profits = [s[1]['profit'] for s in top_sessions]
            session_counts = [s[1]['count'] for s in top_sessions]
            session_colors = ['green' if p > 0 else 'red' for p in session_profits]

            fig_time_session = go.Figure()

            fig_time_session.add_trace(go.Bar(
                x=session_names,
                y=session_profits,
                name='Profit by Time Session',
                marker=dict(color=session_colors),
                text=[f'${p:.2f}<br>({c} trades)' for p, c in zip(session_profits, session_counts)],
                textposition='outside',
                hovertemplate='%{x}<br>Profit: $%{y:.2f}<extra></extra>'
            ))

            fig_time_session.update_layout(
                title=f'Top 10 Most Profitable Time Sessions ({session_duration_hours}h duration)',
                xaxis_title='Time Session',
                yaxis_title='Profit ($)',
                template='plotly_dark',
                height=500,
                showlegend=False,
                xaxis=dict(tickangle=-45)
            )

            fig_time_session_html = fig_time_session.to_html(include_plotlyjs=False, div_id='time_session_chart')

            rows = []
            for idx, (session, data) in enumerate(sorted_sessions[:15], 1):
                avg_profit = data['profit'] / data['count'] if data['count'] > 0 else 0
                profit_color = 'lime' if data['profit'] > 0 else 'red'
                rows.append(f'''
                <tr>
                    <td>{idx}</td>
                    <td><strong>{session}</strong></td>
                    <td style="color: {profit_color}; font-weight: bold;">${data['profit']:.2f}</td>
                    <td>{data['count']}</td>
                    <td style="color: {profit_color};">${avg_profit:.2f}</td>
                </tr>''')

            time_session_table_html = ('<h2>📊 Best Time Sessions Analysis</h2>'
                                       '<div class="table-container"><table>'
                                       '<thead><tr><th>Rank</th><th>Time Session</th><th>Total Profit</th><th>Trades</th><th>Avg Profit/Trade</th></tr></thead>'
                                       '<tbody>' + ''.join(rows) + '</tbody></table></div>')

            if time_session_analysis['best_session']:
                best = time_session_analysis['best_session']
                worst = time_session_analysis['worst_session']
                time_session_table_html += f'''
                <div class="stats-grid" style="margin-top: 20px;">
                    <div class="stat-card">
                        <div class="stat-label">🏆 Best Time Session</div>
                        <div class="stat-value positive">{best[0]}</div>
                        <div class="stat-label">Profit: ${best[1]['profit']:.2f} ({best[1]['count']} trades)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">⚠️ Worst Time Session</div>
                        <div class="stat-value negative">{worst[0]}</div>
                        <div class="stat-label">Loss: ${worst[1]['profit']:.2f} ({worst[1]['count']} trades)</div>
                    </div>
                </div>'''

    chart_price_html = fig_price.to_html(include_plotlyjs='cdn', div_id='price_chart')
    chart_balance_html = fig_balance.to_html(include_plotlyjs=False, div_id='balance_chart')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Forex Backtest Report - {symbol}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: #fff; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border-radius: 20px; padding: 30px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); }}
        h1 {{ text-align: center; margin-bottom: 10px; font-size: 2.5em; background: linear-gradient(45deg, #FFD700, #FFA500); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .subtitle {{ text-align: center; color: #aaa; margin-bottom: 30px; font-size: 1.1em; }}
        .chart-container {{ background: rgba(255, 255, 255, 0.08); border-radius: 15px; padding: 20px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05)); border-radius: 15px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.1); transition: transform 0.3s; }}
        .stat-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3); }}
        .stat-label {{ font-size: 0.9em; color: #aaa; margin-bottom: 10px; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #fff; }}
        .stat-value.positive {{ color: #00ff88; }}
        .stat-value.negative {{ color: #ff4757; }}
        .table-container {{ background: rgba(255, 255, 255, 0.08); border-radius: 15px; padding: 20px; overflow-x: auto; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; color: #fff; }}
        th {{ background: rgba(255, 255, 255, 0.15); padding: 15px; text-align: center; font-weight: 600; border-bottom: 2px solid rgba(255, 255, 255, 0.2); }}
        td {{ padding: 12px; text-align: center; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }}
        tr:hover {{ background: rgba(255, 255, 255, 0.05); }}
        .badge {{ padding: 5px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; display: inline-block; }}
        .badge-buy {{ background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }}
        .badge-sell {{ background: linear-gradient(135deg, #ff4757, #cc3644); color: #fff; }}
        .badge-tp {{ background: linear-gradient(135deg, #ffd700, #ffa500); color: #000; }}
        .badge-sl {{ background: linear-gradient(135deg, #9b59b6, #8e44ad); color: #fff; }}
        .badge-manual {{ background: linear-gradient(135deg, #f39c12, #e67e22); color: #fff; }}
        h2 {{ margin: 30px 0 20px 0; color: #FFD700; font-size: 1.8em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Forex Backtest Report</h1>
        <div class="subtitle">{symbol} | {tf} | {backtest_days} days | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        <div class="chart-container">{chart_price_html}</div>
        <div class="chart-container">{chart_balance_html}</div>
        {f'<div class="chart-container">{fig_weekday_html}</div>' if fig_weekday_html else ''}
        {f'<div class="chart-container">{fig_time_session_html}</div>' if fig_time_session_html else ''}
        {time_session_table_html}
        <h2>General Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">Initial Balance</div><div class="stat-value">${initial_balance:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Final Balance</div><div class="stat-value {'positive' if final_balance > initial_balance else 'negative'}">${final_balance:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Total Profit/Loss</div><div class="stat-value {'positive' if total_profit_usd > 0 else 'negative'}">${total_profit_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">ROI</div><div class="stat-value {'positive' if roi > 0 else 'negative'}">{roi:.2f}%</div></div>
            <div class="stat-card"><div class="stat-label">Max Drawdown</div><div class="stat-value negative">${max_drawdown:.2f} ({max_drawdown_percent:.2f}%)</div></div>
            <div class="stat-card"><div class="stat-label">Max Daily Drawdown</div><div class="stat-value negative">${max_daily_drawdown:.2f} ({max_daily_drawdown_percent:.2f}%)</div></div>
            <div class="stat-card"><div class="stat-label">Sharpe Ratio</div><div class="stat-value">{sharpe_ratio:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Total Trades</div><div class="stat-value">{total_trades}</div></div>
            <div class="stat-card"><div class="stat-label">Win Rate</div><div class="stat-value {'positive' if win_rate >= 50 else 'negative'}">{win_rate:.2f}%</div></div>
            <div class="stat-card"><div class="stat-label">Win Rate (No BE)</div><div class="stat-value">{win_rate_no_breakeven:.2f}%</div></div>
            <div class="stat-card"><div class="stat-label">Profit Factor</div><div class="stat-value">{profit_factor_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Winning Trades</div><div class="stat-value positive">{len(winning_trades)}</div></div>
            <div class="stat-card"><div class="stat-label">Losing Trades</div><div class="stat-value negative">{len(losing_trades)}</div></div>
            <div class="stat-card"><div class="stat-label">Average Win</div><div class="stat-value positive">${avg_win_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Average Loss</div><div class="stat-value negative">${avg_loss_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Average Lot Size</div><div class="stat-value">{avg_lot_size:.2f}</div></div>
        </div>
        <h2>Trade Details</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>#</th><th>Type</th><th>Lot Size</th><th>Entry Time</th><th>Entry Price</th><th>Exit Time</th><th>Exit Price</th><th>Exit Reason</th><th>Profit/Loss</th></tr>
                </thead>
                <tbody>"""

    rows = []
    for idx, p in enumerate(positions, 1):
        usd_color = 'lime' if p['profit_usd'] > 0 else 'red' if p['profit_usd'] < 0 else 'gray'
        exit_badge = 'tp' if p['exit_reason'] == 'TP' else 'sl' if p['exit_reason'] == 'SL' else 'manual'
        rows.append(f"""
                    <tr>
                        <td>{idx}</td>
                        <td><span class="badge badge-{p['type']}">{p['type'].upper()}</span></td>
                        <td>{p['lot_size']:.2f}</td>
                        <td>{p['entry_time']}</td>
                        <td>{p['entry_price']:.5f}</td>
                        <td>{p['exit_time']}</td>
                        <td>{p['exit_price']:.5f}</td>
                        <td><span class="badge badge-{exit_badge}">{p['exit_reason']}</span></td>
                        <td style="color: {usd_color}; font-weight: bold;">${p['profit_usd']:.2f}</td>
                    </tr>""")

    html += ''.join(rows) + """
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""

    os.makedirs('backtest', exist_ok=True)
    filename = f"backtest/backtest_report_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Backtest completed! Report saved to: {filename}")

    return filename

def optimize_strategy(df, trigger_signals, confirmation_signals, symbol, tf,
                     backtest_days, initial_balance,
                     position_size_mode, fixed_lot_size,
                     risk_percent, risk_based_on,
                     optimization_params):

    use_risk_free_options = optimization_params.get('use_risk_free', [True, False])
    use_sl_options = optimization_params.get('use_sl', [True, False])
    use_tp_options = optimization_params.get('use_tp', [True, False])
    close_opposite_options = optimization_params.get('close_opposite_position', [True, False])

    def pip_range(name, start, end, step, default):
        params = optimization_params.get(name, {})
        if not params:
            return [default]
        return list(range(params.get('start', start), params.get('end', end) + 1, params.get('step', step)))

    risk_free_values = pip_range('risk_free_distance_pips', 10, 50, 10, 20)
    sl_values = pip_range('sl_pips', 20, 100, 20, 50)
    tp_values = pip_range('tp_pips', 30, 150, 30, 100)

    param_combinations = [
        {
            'use_risk_free': use_rf,
            'risk_free_distance_pips': rf_dist,
            'use_sl': use_sl_val,
            'sl_pips': sl_val,
            'use_tp': use_tp_val,
            'tp_pips': tp_val,
            'close_opposite_position': close_opp
        }
        for use_rf in use_risk_free_options
        for rf_dist in (risk_free_values if use_rf else [0])
        for use_sl_val in use_sl_options
        for sl_val in (sl_values if use_sl_val else [0])
        for use_tp_val in use_tp_options
        for tp_val in (tp_values if use_tp_val else [0])
        for close_opp in close_opposite_options
    ]

    print(f"Starting optimization with {len(param_combinations)} combinations...")

    results = []
    total = len(param_combinations)

    for idx, params in enumerate(param_combinations, 1):
        try:
            result_data = run_backtest(
                df, trigger_signals, confirmation_signals,
                symbol, tf, backtest_days,
                params['use_risk_free'],
                params['risk_free_distance_pips'],
                params['use_sl'],
                params['sl_pips'],
                params['use_tp'],
                params['tp_pips'],
                params['close_opposite_position'],
                initial_balance,
                position_size_mode,
                fixed_lot_size,
                risk_percent,
                risk_based_on
            )

            if result_data:
                results.append({
                    'params': params,
                    'metrics': result_data,
                    'status': 'success'
                })
            else:
                results.append({
                    'params': params,
                    'status': 'no_trades'
                })

        except Exception as e:
            print(f"Error in combo {idx}: {str(e)}")
            results.append({
                'params': params,
                'error': str(e),
                'status': 'failed'
            })

        if idx % 10 == 0 or idx == total:
            print(f"Progress: {idx}/{total}")

    print("Optimization completed!")

    analyze_results(results, symbol, tf, backtest_days)

    return results

def run_backtest(df, trigger_signals, confirmation_signals, symbol, tf,
                backtest_days, use_risk_free, risk_free_distance_pips,
                use_sl, sl_pips, use_tp, tp_pips, close_opposite_position,
                initial_balance, position_size_mode, fixed_lot_size,
                risk_percent, risk_based_on):

    if len(df) == 0:
        return None

    result = _simulate(_context(df, symbol, tf), trigger_signals, confirmation_signals,
                       use_risk_free, risk_free_distance_pips, use_sl, sl_pips, use_tp, tp_pips,
                       close_opposite_position, initial_balance, position_size_mode, fixed_lot_size,
                       risk_percent, risk_based_on)

    profits = [tr[6] for tr in result['trades']]
    if len(profits) == 0:
        return None

    total_trades = len(profits)
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]

    total_profit_usd = sum(profits)
    final_balance = initial_balance + total_profit_usd

    win_rate = len(wins) / total_trades * 100

    gross_profit_usd = sum(wins) if wins else 0
    gross_loss_usd = abs(sum(losses)) if losses else 0

    roi = ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0
    profit_factor_usd = (gross_profit_usd / gross_loss_usd) if gross_loss_usd > 0 else float('inf')
    peak_balance = result['peak_balance']
    max_drawdown_percent = (result['realized_max_drawdown'] / peak_balance * 100) if peak_balance > 0 else 0

    return {
        'roi': roi,
        'winrate': win_rate,
        'total_trades': total_trades,
        'profit_factor': profit_factor_usd,
        'max_drawdown': max_drawdown_percent,
        'final_balance': final_balance,
        'total_profit': total_profit_usd
    }

def analyze_results(results, symbol, tf, backtest_days):

    data = []
    for i, res in enumerate(results, 1):
        if res['status'] != 'success':
            continue

        params = res['params']
        metrics = res['metrics']

        data.append({
            'id': i,
            'use_risk_free': params['use_risk_free'],
            'risk_free_pips': params['risk_free_distance_pips'],
            'use_sl': params['use_sl'],
            'sl_pips': params['sl_pips'],
            'use_tp': params['use_tp'],
            'tp_pips': params['tp_pips'],
            'close_opposite': params['close_opposite_position'],
            'roi': metrics['roi'],
            'winrate': metrics['winrate'],
            'total_trades': metrics['total_trades'],
            'profit_factor': metrics['profit_factor'],
            'max_drawdown': metrics['max_drawdown']
        })

    if len(data) == 0:
        print("No successful results found!")
        return None

    df_results = pd.DataFrame(data)

    top_roi = df_results.nlargest(5, 'roi')
    top_winrate = df_results.nlargest(5, 'winrate')

    common_ids = set(top_roi['id']).intersection(set(top_winrate['id']))
    best_setups = df_results[df_results['id'].isin(common_ids)]

    html = generate_optimization_report(df_results, top_roi, top_winrate, best_setups, symbol, tf, backtest_days)

    os.makedirs('optimize', exist_ok=True)
    filename = f"optimize/optimize_report_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Report saved: {filename}")
    return filename

def _badge(value):
    return f'<span class="badge badge-{"yes" if value else "no"}">{"Yes" if value else "No"}</span>'

def generate_optimization_report(df_all, top_roi, top_winrate, best_setups, symbol, tf, days):
    html = f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Optimization Report - {symbol}</title>
<style>
* {{margin:0;padding:0;box-sizing:border-box}}
body {{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%);color:#fff;padding:20px}}
.container {{max-width:1800px;margin:0 auto;background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);border-radius:20px;padding:30px;box-shadow:0 8px 32px rgba(0,0,0,0.4)}}
h1 {{text-align:center;margin-bottom:10px;font-size:3em;background:linear-gradient(45deg,#00f2fe,#4facfe);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.subtitle {{text-align:center;color:#aaa;margin-bottom:40px;font-size:1.2em}}
h2 {{margin:40px 0 20px 0;color:#00f2fe;font-size:2em;border-bottom:2px solid rgba(0,242,254,0.3);padding-bottom:10px}}
.section {{background:rgba(255,255,255,0.08);border-radius:15px;padding:25px;margin-bottom:30px;box-shadow:0 4px 15px rgba(0,0,0,0.3)}}
table {{width:100%;border-collapse:collapse;margin-top:20px;font-size:0.9em}}
th {{background:rgba(0,242,254,0.2);padding:12px 8px;text-align:center;font-weight:600;border-bottom:2px solid rgba(0,242,254,0.5);white-space:nowrap}}
td {{padding:10px 8px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.1)}}
tr:hover {{background:rgba(255,255,255,0.05)}}
.badge {{padding:5px 10px;border-radius:20px;font-size:0.8em;font-weight:bold;display:inline-block;white-space:nowrap}}
.badge-yes {{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000}}
.badge-no {{background:linear-gradient(135deg,#ff4757,#cc3644);color:#fff}}
.stats-grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin-bottom:30px}}
.stat-card {{background:linear-gradient(135deg,rgba(0,242,254,0.15),rgba(79,172,254,0.1));border-radius:15px;padding:20px;border:1px solid rgba(0,242,254,0.3);transition:transform 0.3s}}
.stat-card:hover {{transform:translateY(-5px);box-shadow:0 8px 25px rgba(0,242,254,0.3)}}
.stat-label {{font-size:0.95em;color:#aaa;margin-bottom:10px}}
.stat-value {{font-size:2.5em;font-weight:bold;color:#00f2fe}}
.positive {{color:#00ff88!important}}
.negative {{color:#ff4757!important}}
.crown {{font-size:1.3em;margin-right:5px}}
</style>
</head>
<body>
<div class="container">
<h1>Strategy Optimization Report</h1>
<div class="subtitle">{symbol} | {tf} | {days} days | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div class="stats-grid">
<div class="stat-card"><div class="stat-label">Total Combinations</div><div class="stat-value">{len(df_all)}</div></div>
<div class="stat-card"><div class="stat-label">Best ROI</div><div class="stat-value positive">{top_roi.iloc[0]['roi']:.2f}%</div></div>
<div class="stat-card"><div class="stat-label">Best Win Rate</div><div class="stat-value positive">{top_winrate.iloc[0]['winrate']:.2f}%</div></div>
<div class="stat-card"><div class="stat-label">Common Best Setups</div><div class="stat-value" style="color:#ffd700">{len(best_setups)}</div></div>
</div>
<div class="section">
<h2>Top 5 Setups by ROI</h2>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>Rank</th>
<th>Risk Free</th>
<th>RF Pips</th>
<th>Stop Loss</th>
<th>SL Pips</th>
<th>Take Profit</th>
<th>TP Pips</th>
<th>Close Opposite</th>
<th>ROI</th>
<th>Win Rate</th>
<th>Trades</th>
<th>PF</th>
</tr>
</thead>
<tbody>"""

    for rank, (_, row) in enumerate(top_roi.iterrows(), 1):
        html += f"""
<tr>
<td><span class="crown">{'👑' if rank==1 else '🏅'}</span>{rank}</td>
<td>{_badge(row['use_risk_free'])}</td>
<td>{row['risk_free_pips']:.0f}</td>
<td>{_badge(row['use_sl'])}</td>
<td>{row['sl_pips']:.0f}</td>
<td>{_badge(row['use_tp'])}</td>
<td>{row['tp_pips']:.0f}</td>
<td>{_badge(row['close_opposite'])}</td>
<td class="positive" style="font-weight:bold">{row['roi']:.2f}%</td>
<td>{row['winrate']:.2f}%</td>
<td>{row['total_trades']:.0f}</td>
<td>{row['profit_factor']:.2f}</td>
</tr>"""

    html += """
</tbody>
</table>
</div>
</div>
<div class="section">
<h2>Top 5 Setups by Win Rate</h2>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>Rank</th>
<th>Risk Free</th>
<th>RF Pips</th>
<th>Stop Loss</th>
<th>SL Pips</th>
<th>Take Profit</th>
<th>TP Pips</th>
<th>Close Opposite</th>
<th>Win Rate</th>
<th>ROI</th>
<th>Trades</th>
<th>PF</th>
</tr>
</thead>
<tbody>"""

    for rank, (_, row) in enumerate(top_winrate.iterrows(), 1):
        html += f"""
<tr>
<td><span class="crown">{'👑' if rank==1 else '🏅'}</span>{rank}</td>
<td>{_badge(row['use_risk_free'])}</td>
<td>{row['risk_free_pips']:.0f}</td>
<td>{_badge(row['use_sl'])}</td>
<td>{row['sl_pips']:.0f}</td>
<td>{_badge(row['use_tp'])}</td>
<td>{row['tp_pips']:.0f}</td>
<td>{_badge(row['close_opposite'])}</td>
<td class="positive" style="font-weight:bold">{row['winrate']:.2f}%</td>
<td>{row['roi']:.2f}%</td>
<td>{row['total_trades']:.0f}</td>
<td>{row['profit_factor']:.2f}</td>
</tr>"""

    html += """
</tbody>
</table>
</div>
</div>"""

    if len(best_setups) > 0:
        html += """
<div class="section">
<h2>Common Best Setups</h2>
<p style="color:#ffd700;margin-bottom:20px;font-size:1.1em">These setups have both high ROI and excellent Win Rate</p>
<div style="overflow-x:auto">
<table>
<thead>
<tr style="background:rgba(255,215,0,0.2)">
<th>Risk Free</th>
<th>RF Pips</th>
<th>Stop Loss</th>
<th>SL Pips</th>
<th>Take Profit</th>
<th>TP Pips</th>
<th>Close Opposite</th>
<th>ROI</th>
<th>Win Rate</th>
<th>Trades</th>
<th>PF</th>
<th>Max DD</th>
</tr>
</thead>
<tbody>"""

        for _, row in best_setups.iterrows():
            html += f"""
<tr style="background:rgba(255,215,0,0.1)">
<td>{_badge(row['use_risk_free'])}</td>
<td>{row['risk_free_pips']:.0f}</td>
<td>{_badge(row['use_sl'])}</td>
<td>{row['sl_pips']:.0f}</td>
<td>{_badge(row['use_tp'])}</td>
<td>{row['tp_pips']:.0f}</td>
<td>{_badge(row['close_opposite'])}</td>
<td class="positive" style="font-weight:bold">{row['roi']:.2f}%</td>
<td class="positive" style="font-weight:bold">{row['winrate']:.2f}%</td>
<td>{row['total_trades']:.0f}</td>
<td>{row['profit_factor']:.2f}</td>
<td class="negative">{row['max_drawdown']:.2f}%</td>
</tr>"""

        html += """
</tbody>
</table>
</div>
</div>"""
    else:
        html += """
<div class="section">
<h2>Common Best Setups</h2>
<p style="color:#ff4757;font-size:1.2em;text-align:center;padding:30px">No common setups found</p>
</div>"""

    html += """
</div>
</body>
</html>"""
    return html

def convert_to_heikin_ashi(result: pd.DataFrame) -> pd.DataFrame:
    ha_result = result.copy()
    if len(result):
        ohlc = (result[c].to_numpy(dtype=np.float64) for c in ('open', 'high', 'low', 'close'))
        ha_result['open'], ha_result['high'], ha_result['low'], ha_result['close'] = _heikin_ashi(*ohlc)
    return ha_result

def backtest_candle(symbol: str, timeframe: str = "1m", limit: int = 100, heikin_ashi: bool = False):

    tf = timeframe_seconds(timeframe)
    df = _store(symbol).candles(tf, max(int(limit), 0), heikin_ashi)

    if df.empty:
        print(f"Warning: No tick data returned from MT5 for {symbol} on {timeframe}")

    return df

def extract_number(string):

    match = re.search(r'\d+', string)
    if match:
        return float(match.group())
    else:
        raise ValueError("no number found in string")
