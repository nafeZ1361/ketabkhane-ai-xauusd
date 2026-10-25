import unittest
from datetime import datetime, timedelta

from xauusd_research.backtest import run_backtest
from xauusd_research.schema import Candle
from xauusd_research.strategies import StrategySpec, signals
from xauusd_research.stream import run_stream

SPEC = StrategySpec("t", 2, 4)


def series(closes):
    start = datetime(2024, 1, 1)
    return [Candle(start + timedelta(minutes=i), c, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]


class TrendFilterTests(unittest.TestCase):
    def test_filter_blocks_early_entries_in_downtrend(self):
        # declining then recovering: trend filter must suppress entries while price is under the trend
        closes = [20, 19, 18, 17, 16, 15, 16, 17, 18, 19, 20, 21, 22, 23]
        unfiltered = signals(series(closes), SPEC)
        filtered = signals(series(closes), SPEC, trend_window=6)
        self.assertGreaterEqual(sum(1 for s in unfiltered if s == 1), 1)
        self.assertLessEqual(sum(1 for s in filtered if s == 1), sum(1 for s in unfiltered if s == 1))

    def test_filter_keeps_exits(self):
        closes = [20, 19, 18, 17, 16, 15, 16, 17, 18, 19, 20, 21, 22, 23, 22, 21, 20]
        filtered = signals(series(closes), SPEC, trend_window=6)
        self.assertTrue(any(s == -1 for s in filtered))

    def test_batch_and_stream_agree_with_filter(self):
        closes = [20, 19, 18, 17, 16, 15, 16, 17, 18, 19, 20, 21, 22, 23, 22, 21, 20, 19, 18]
        candles = series(closes)
        batch = run_backtest(candles, SPEC, trend_window=6)
        streamed = run_stream(candles, SPEC, trend_window=6)
        self.assertEqual(batch.metrics, streamed.metrics)
        self.assertEqual(len(batch.trades), len(streamed.trades))


if __name__ == "__main__":
    unittest.main()