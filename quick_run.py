from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from xauusd_research.schema import load_candles
from xauusd_research.strategies import STRATEGY_BY_NAME
from xauusd_research.costs import BrokerProfile
from xauusd_research.backtest import run_backtest

def main():
    print('=' * 60)
    print('  XAUUSD Quantitative Research Quickstart Runner')
    print('=' * 60)
    fixture_path = ROOT / 'tests' / 'fixtures' / 'synthetic_500.csv'
    profile_path = ROOT / 'config' / 'scenario_s3.json'
    candles = load_candles(fixture_path, tz_policy='eu-dst')
    print(f'> Loaded {len(candles)} candles from {fixture_path.name}')
    profile = BrokerProfile.load(profile_path)
    print(f'> Broker Profile: {profile.profile_id} (Cost: {profile.cost_per_trade():.2f} USD)')
    spec = STRATEGY_BY_NAME['ma_100_400']
    trend_window = 500
    print(f'> Running Strategy: {spec.name} + Trend {trend_window}...')
    result = run_backtest(candles, spec, profile=profile, trend_window=trend_window)
    m = result.metrics
    print('-' * 60)
    print(f'  Trades       : {m["trades"]}')
    print(f'  Net PnL      : {m["net_pnl"]} USD')
    print(f'  Win Rate     : {m["win_rate"] * 100:.1f} %')
    print(f'  Profit Factor: {m["profit_factor"]:.2f}')
    print(f'  Max Drawdown : {m["max_drawdown"]} USD')
    print('=' * 60)
    print('Execution completed smoothly with ZERO errors!')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
