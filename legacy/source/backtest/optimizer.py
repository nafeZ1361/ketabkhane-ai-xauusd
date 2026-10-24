from .hashem_backtest import *
from .hashem_backtest import _context, _simulate
from .indicators import *
import itertools
import threading
from tqdm import tqdm
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import os


DEFAULT_PARAMS = {
    'ema': {
        'window': [5 , 10 , 15, 20 , 30 , 40, 50 , 70, 100 , 150 , 170 , 200]
    },
    'ema_cross': {
        'fast_period': [10,15, 20,25 , 30 , 35 ,40 , 45, 50],
        'slow_period': [20 , 30 , 40, 50, 70 , 90 , 100,130 , 150, 170 , 200]
    },
    'macd': {
        'fast': [10 , 12 , 15, 17 , 20],
        'slow': [10 , 21, 26, 34 , 50],
        'signal': [5, 9, 13]
    },
    'super_trend': {
        'atr_period': [5, 10 , 12 ,13 ,14, 15, 20],
        'multiplier': [2.0, 3.0, 4.0 , 5.0]
    },
    'ut_bot': {
        'key_value': [2, 3, 4, 5 , 6, 7],
        'atr_period': [8, 10, 12, 14 , 16]
    },
    'kalman_trend': {
        'sell_len': [5 , 10 , 20 , 30 ,40 , 50 , 60, 70 , 80],
        'buy_len': [50 ,70 ,100, 150, 200]
    },
    'trend_ali': {
        'length': [60],
        'length_mult': [6.0],
        'mode': ['Hma']
    },
    'half_trend': {
        'amplitude': [2, 3, 4 , 5 ,6],
        'channel_deviation': [2, 3]
    },
    'volumatic_vidya': {
        'vidya_length': [8, 10, 12],
        'vidya_momentum': [15, 20, 25],
        'band_distance': [1.5, 2.0, 2.5]
    },
    'deviation_trend': {
        'sma_length': [10 , 20 ,30, 40 , 50, 70]
    },
    'stoch_rsi': {
        'rsi_length': [9, 14, 21],
        'stoch_length': [9, 14, 21],
        'k_period': [3, 5, 7],
        'd_period': [3, 5, 7]
    }
}

_INDICATOR_NAMES = {'super_trend': 'supertrend', 'stoch_rsi': 'stochrsi'}
_DEFAULT_PARAM_KEYS = {v: k for k, v in _INDICATOR_NAMES.items()}
_CONFIRMATION_CACHE = {}
_CONFIRMATION_LOCK = threading.Lock()


def get_indicator_signals(df, symbol, tf , indicator_name, params):
    name = _INDICATOR_NAMES.get(indicator_name, indicator_name)
    limit = len(df)
    try:
        if name == 'ema':
            signals = backtest_ema(symbol, tf, params.get('window', 20), limit, df=df)
            return signals, signals

        if name == 'macd':
            fast, slow = params.get('fast', 12), params.get('slow', 26)
            if fast >= slow:
                return None, None
            histogram = backtest_macd(symbol, tf, limit, fast, slow, params.get('signal', 9), df=df)['histogram']
            signals = ['buy' if h > 0 else 'sell' if h < 0 else 'hold' for h in histogram]
            return signals, signals

        if name == 'stochrsi':
            args = (params.get('rsi_length', 14), params.get('stoch_length', 14),
                    params.get('k_period', 3), params.get('d_period', 3))
            k_line = backtest_stochrsi(symbol, tf, limit, 'blue', *args, df=df)
            d_line = backtest_stochrsi(symbol, tf, limit, 'red', *args, df=df)
            signals = ['buy' if k > d else 'sell' if k < d else 'hold' for k, d in zip(k_line, d_line)]
            return signals, signals

        if name == 'ema_cross':
            fast, slow = params.get('fast_period', 20), params.get('slow_period', 50)
            if fast >= slow:
                return None, None
            result = backtest_ema_cross(symbol, tf, limit, fast, slow, df=df)
        elif name == 'supertrend':
            result = backtest_supertrend(symbol, tf, limit, params.get('atr_period', 10), params.get('multiplier', 3.0), df=df)
        elif name == 'ut_bot':
            result = backtest_ut_bot(symbol, tf, limit, params.get('key_value', 3), params.get('atr_period', 10), df=df)
        elif name == 'kalman_trend':
            sell_len, buy_len = params.get('sell_len', 50), params.get('buy_len', 150)
            if sell_len >= buy_len:
                return None, None
            result = backtest_kalman_trend_levels(symbol, tf, limit, sell_len, buy_len, df=df)
        elif name == 'trend_ali':
            result = backtest_trend_ali(symbol, tf, limit, params.get('length', 60), params.get('length_mult', 6.0), params.get('mode', 'Hma'), df=df)
        elif name == 'half_trend':
            result = backtest_half_trend(symbol, tf, limit, params.get('amplitude', 2), params.get('channel_deviation', 2), df=df)
        elif name == 'volumatic_vidya':
            result = backtest_volumatic_vidya(symbol, tf, limit, params.get('vidya_length', 10), params.get('vidya_momentum', 20), params.get('band_distance', 2), df=df)
        elif name == 'deviation_trend':
            result = backtest_deviation_trend_signals(symbol, tf, limit, params.get('sma_length', 50), df=df)
        else:
            raise ValueError(f"Indicator {indicator_name} not supported")

        return result['signal'], result['trend']

    except Exception:
        return None, None


def _confirmation_signals(df, symbol, tf, indicator_name, params):
    key = (symbol, tf, len(df), df['time'].iloc[0], df['time'].iloc[-1], indicator_name,
           json.dumps(params, sort_keys=True, default=str))
    with _CONFIRMATION_LOCK:
        if key not in _CONFIRMATION_CACHE:
            _CONFIRMATION_CACHE[key] = get_indicator_signals(df, symbol, tf, indicator_name, params)[1]
        return _CONFIRMATION_CACHE[key]


def backtest_opt(df, trigger_signals, confirmation_signals, symbol, tf,
             backtest_days, use_risk_free, risk_free_distance_pips,
             use_sl, sl_pips, use_tp, tp_pips,
             close_opposite_position, initial_balance,
             position_size_mode, fixed_lot_size,
             risk_percent, risk_based_on,
             analyze_weekdays, analyze_time_sessions,
             session_duration_hours):

    if len(df) == 0 or len(df) != len(trigger_signals) or len(df) != len(confirmation_signals):
        return None

    result = _simulate(_context(df, symbol, tf), trigger_signals, confirmation_signals,
                       use_risk_free, risk_free_distance_pips, use_sl, sl_pips, use_tp, tp_pips,
                       close_opposite_position, initial_balance, position_size_mode, fixed_lot_size,
                       risk_percent, risk_based_on)

    profits = [tr[6] for tr in result['trades']]
    if len(profits) == 0:
        return None

    total_trades = len(profits)
    final_balance = initial_balance + sum(profits)

    return {
        'win_rate': sum(1 for p in profits if p > 0) / total_trades * 100,
        'capital_increase_percent': ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0,
        'total_trades': total_trades,
        'max_drawdown_percent': result['max_drawdown_percent'],
        'final_balance': final_balance
    }


def _aligned_signals(df, symbol, tf, entry_indicator, entry_params_dict, conf_indicator, fixed_conf_params):
    entry_signals, _ = get_indicator_signals(df, symbol, tf, entry_indicator, entry_params_dict)
    if entry_signals is None:
        return None

    if conf_indicator:
        confirmation = _confirmation_signals(df, symbol, tf, conf_indicator, fixed_conf_params or {})
    else:
        confirmation = entry_signals
    if confirmation is None:
        return None

    min_len = min(len(entry_signals), len(confirmation), len(df))
    if min_len == 0:
        return None
    df_sliced = df if min_len == len(df) else df.iloc[-min_len:].reset_index(drop=True)
    return df_sliced, entry_signals[-min_len:], confirmation[-min_len:]


def test_single_combination(args):
    df, symbol, tf, entry_indicator, entry_combo, entry_param_names, conf_indicator, fixed_conf_params, backtest_params = args

    entry_params_dict = dict(zip(entry_param_names, entry_combo))

    try:
        aligned = _aligned_signals(df, symbol, tf, entry_indicator, entry_params_dict, conf_indicator, fixed_conf_params)
        if aligned is None:
            return None

        result = backtest_opt(*aligned, **backtest_params)
        if result is None:
            return None

        return {
            'params': entry_params_dict,
            'win_rate': result['win_rate'],
            'roi': result['capital_increase_percent'],
            'total_trades': result['total_trades'],
            'max_drawdown': result['max_drawdown_percent'],
            'final_balance': result['final_balance']
        }

    except Exception:
        return None


def _evaluate_out_of_sample(df_full, split_index, symbol, tf, entry_indicator, best_params,
                            conf_indicator, fixed_conf_params, backtest_params, warmup_bars=1000):
    start = max(0, split_index - warmup_bars)
    aligned = _aligned_signals(df_full.iloc[start:].reset_index(drop=True), symbol, tf, entry_indicator,
                               best_params, conf_indicator, fixed_conf_params)
    if aligned is None:
        return None

    df_ext, entry_signals, confirmation = aligned
    drop_n = int((df_ext['time'] < df_full['time'].iloc[split_index]).sum())
    if len(df_ext) - drop_n < 2:
        return None

    return backtest_opt(df_ext.iloc[drop_n:].reset_index(drop=True), entry_signals[drop_n:],
                        confirmation[drop_n:], **backtest_params)


def optimizer(symbol, tf , backtest_days, entry_indicator, entry_params=None, conf_indicator=None, fixed_conf_params=None, max_workers=4, train_ratio=1.0):

    print("\n" + "="*80)
    print(f"🚀 OPTIMIZER STARTED")
    print("="*80)
    print(f"Symbol: {symbol} | Timeframe: {tf} | Backtest Days: {backtest_days}")
    print(f"Entry Indicator: {entry_indicator}")
    if conf_indicator:
        print(f"Confirmation Indicator: {conf_indicator}")
    print("="*80 + "\n")

    reset_tick_data(symbol)
    _CONFIRMATION_CACHE.clear()

    limit = int(backtest_days * 1440 / (timeframe_seconds(tf) / 60))

    print("📊 Loading MT5 tick data...")
    df = backtest_candle(symbol, tf, limit)
    if df.empty:
        print("❌ No tick data available!")
        print("="*80 + "\n")
        return {'error': 'هیچ نتیجه معتبری یافت نشد'}
    print(f"✅ Loaded {len(df)} candles built from {len(_context(df, symbol, tf).t)} ticks\n")

    split_index = len(df)
    optimization_df = df
    if train_ratio < 1.0:
        split_index = int(len(df) * train_ratio)
        optimization_df = df.iloc[:split_index].reset_index(drop=True)
        print(f"🔒 Train/Test split enabled: optimizing on first {train_ratio*100:.0f}% "
              f"({len(optimization_df)} candles), holding out last {(1-train_ratio)*100:.0f}% "
              f"({len(df) - split_index} candles) for out-of-sample validation.\n")

    if entry_params is None:
        entry_params = DEFAULT_PARAMS.get(entry_indicator) or DEFAULT_PARAMS.get(_DEFAULT_PARAM_KEYS.get(entry_indicator), {})

    entry_param_names = list(entry_params.keys())
    entry_combinations = list(itertools.product(*entry_params.values()))

    total_combinations = len(entry_combinations)
    print(f"🔍 Total combinations to test: {total_combinations}\n")

    backtest_params = {
        'symbol': symbol,
        'tf': tf,
        'backtest_days': backtest_days,
        'use_risk_free': False,
        'risk_free_distance_pips': 50,
        'use_sl': True,
        'sl_pips': 500,
        'use_tp': True,
        'tp_pips': 1000,
        'close_opposite_position': False,
        'initial_balance': 5000,
        'position_size_mode': 'risk_percent',
        'fixed_lot_size': 0.01,
        'risk_percent': 2,
        'risk_based_on': 'initial',
        'analyze_weekdays': False,
        'analyze_time_sessions': False,
        'session_duration_hours': 4.0
    }

    best_result = {
        'params': None,
        'win_rate': -1,
        'roi': -float('inf'),
        'total_trades': 0,
        'max_drawdown': 0,
        'final_balance': 0
    }

    valid_results = 0

    print(f"⚡ Starting optimization with {max_workers} workers...\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(test_single_combination,
                            (optimization_df, symbol, tf, entry_indicator, combo, entry_param_names, conf_indicator, fixed_conf_params, backtest_params))
            for combo in entry_combinations
        ]

        with tqdm(total=total_combinations, desc="Testing combinations", ncols=100) as pbar:
            for future in as_completed(futures):
                result = future.result()

                if result is not None:
                    valid_results += 1

                    if result['roi'] > best_result['roi'] or \
                       (result['roi'] == best_result['roi'] and result['win_rate'] > best_result['win_rate']):
                        best_result = result

                        pbar.set_postfix({
                            'Best ROI': f"{best_result['roi']:.2f}%",
                            'Win Rate': f"{best_result['win_rate']:.1f}%",
                            'Valid': valid_results
                        })

                pbar.update(1)

    print("\n" + "="*80)

    if best_result['params'] is None:
        print("❌ No valid results found!")
        print("="*80 + "\n")
        return {'error': 'هیچ نتیجه معتبری یافت نشد'}

    oos_result = None
    if train_ratio < 1.0:
        print("🧪 Validating best parameters on held-out (unseen) data...")
        try:
            oos_result = _evaluate_out_of_sample(
                df, split_index, symbol, tf, entry_indicator, best_result['params'],
                conf_indicator, fixed_conf_params, backtest_params
            )
        except Exception:
            oos_result = None
        if oos_result is None:
            print("⚠️  Could not produce an out-of-sample result (e.g. no trades triggered "
                  "in the held-out window). Treat the in-sample result with extra caution.\n")
        else:
            print(f"   In-Sample  (train) ROI: {best_result['roi']:.2f}%  |  Win Rate: {best_result['win_rate']:.2f}%  |  Trades: {best_result['total_trades']}")
            print(f"   Out-of-Sample (test) ROI: {oos_result['capital_increase_percent']:.2f}%  |  Win Rate: {oos_result['win_rate']:.2f}%  |  Trades: {oos_result['total_trades']}")
            if oos_result['capital_increase_percent'] <= 0 or oos_result['total_trades'] < 5:
                print("   ⚠️  Out-of-sample performance is weak/negative or has too few trades - "
                      "this is a strong sign the in-sample result is overfit to that window's noise.")
            print()

    result_data = {
        'symbol': symbol,
        'timeframe': tf,
        'backtest_days': backtest_days,
        'entry_indicator': entry_indicator,
        'confirmation_indicator': conf_indicator,
        'best_parameters': best_result['params'],
        'win_rate': best_result['win_rate'],
        'roi': best_result['roi'],
        'total_trades': best_result['total_trades'],
        'max_drawdown': best_result['max_drawdown'],
        'final_balance': best_result['final_balance'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_combinations_tested': total_combinations,
        'valid_results': valid_results,
        'train_ratio': train_ratio,
        'out_of_sample': {
            'win_rate': oos_result['win_rate'],
            'roi': oos_result['capital_increase_percent'],
            'total_trades': oos_result['total_trades'],
            'max_drawdown': oos_result['max_drawdown_percent'],
            'final_balance': oos_result['final_balance']
        } if oos_result else None
    }

    os.makedirs('optimizer_results', exist_ok=True)
    filename = f"optimizer_results/best_params_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=4, ensure_ascii=False)

    print("✅ OPTIMIZATION COMPLETED!")
    print("="*80)
    print(f"📊 Results Summary:")
    print(f"   Valid combinations tested: {valid_results}/{total_combinations}")
    print(f"\n🏆 Best Parameters:")
    for key, value in best_result['params'].items():
        print(f"   {key}: {value}")
    print(f"\n📈 Performance Metrics:")
    print(f"   Win Rate: {best_result['win_rate']:.2f}%")
    print(f"   ROI: {best_result['roi']:.2f}%")
    print(f"   Total Trades: {best_result['total_trades']}")
    print(f"   Max Drawdown: {best_result['max_drawdown']:.2f}%")
    print(f"   Final Balance: ${best_result['final_balance']:.2f}")
    print(f"\n💾 Results saved to: {filename}")
    print("="*80 + "\n")

    return best_result['params']


if __name__ == "__main__":

    symbol = 'XAUUSD.'
    tf = '3m'
    BACKTEST_DAYS = 30
    
    # Optional: Fixed confirmation parameters
    # config = {
    #     'amplitude': 2,
    #     'channel_deviation': 2
    # }
    
    result = optimizer(
        symbol=symbol,
        tf=tf,
        backtest_days=BACKTEST_DAYS,
        entry_indicator='kalman_trend',
        conf_indicator='trend_ali',
        # fixed_conf_params=config,
    )

    print("🎯 Final Output (Best Parameters):")
    print(result)
