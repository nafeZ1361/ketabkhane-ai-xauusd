import unittest
from datetime import datetime, timedelta

from xauusd_research.backtest import COST_LABEL_NO_COSTS, Trade, compute_metrics, run_backtest
from xauusd_research.schema import Candle
from xauusd_research.strategies import StrategySpec

SPEC = StrategySpec("t", 2, 4)


def series(closes):
    start = datetime(2024, 1, 1)
    return [Candle(start + timedelta(minutes=i), c, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]


class BacktestTests(unittest.TestCase):
    def test_single_trade_uses_next_bar_open(self):
        closes = [10, 10, 10, 10, 10, 11, 12, 13, 12, 11, 10, 9, 8]
        result = run_backtest(series(closes), SPEC)
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual(trade.entry_price, 12.0)
        self.assertEqual(trade.exit_price, 10.0)
        self.assertEqual(trade.pnl, -2.0)
        self.assertEqual(trade.reason, "signal")
        self.assertEqual(result.label, COST_LABEL_NO_COSTS)

    def test_open_position_is_closed_at_end(self):
        closes = [10, 10, 10, 10, 10, 11, 12, 13]
        result = run_backtest(series(closes), SPEC)
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].reason, "end_of_data")
        self.assertEqual(result.trades[0].entry_price, 12.0)
        self.assertEqual(result.trades[0].exit_price, 13.0)

    def test_metrics_are_computed(self):
        trades = [Trade(None, None, 0, 0, 5.0, 1, "signal"), Trade(None, None, 0, 0, -3.0, 1, "signal")]
        metrics = compute_metrics(trades, [0.0, 5.0, 2.0])
        self.assertEqual(metrics["trades"], 2)
        self.assertEqual(metrics["net_pnl"], 2.0)
        self.assertAlmostEqual(metrics["win_rate"], 0.5)
        self.assertAlmostEqual(metrics["profit_factor"], 5 / 3)
        self.assertEqual(metrics["max_drawdown"], 3.0)

    def test_metrics_without_trades(self):
        metrics = compute_metrics([], [0.0])
        self.assertEqual(metrics, {"trades": 0, "net_pnl": 0.0, "win_rate": 0.0,
                                   "profit_factor": 0.0, "max_drawdown": 0.0})

    def test_no_signals_produces_no_trades(self):
        result = run_backtest(series([10, 11, 12, 13, 14]), SPEC)
        self.assertEqual(result.trades, [])


if __name__ == "__main__":
    unittest.main()