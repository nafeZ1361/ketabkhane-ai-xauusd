import unittest
from datetime import datetime, timedelta

from xauusd_research.schema import Candle
from xauusd_research.strategies import STRATEGY_BY_NAME, STRATEGIES, StrategySpec, signals, sma


def series(closes):
    start = datetime(2024, 1, 1)
    return [Candle(start + timedelta(minutes=i), c, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]


class StrategyTests(unittest.TestCase):
    def test_strategies_are_defined(self):
        self.assertGreaterEqual(len(STRATEGIES), 5)
        for name in ("ma_5_20", "ma_10_50", "ma_20_100", "ma_50_200", "ma_100_400"):
            self.assertIn(name, STRATEGY_BY_NAME)

    def test_sma_values(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 3), [None, None, 2.0, 3.0, 4.0])

    def test_sma_rejects_bad_window(self):
        with self.assertRaises(ValueError):
            sma([1, 2], 0)

    def test_crosses_are_detected(self):
        closes = [10, 10, 10, 10, 10, 11, 12, 13, 12, 11, 10, 9, 8, 9, 10, 11]
        sig = signals(series(closes), StrategySpec("t", 2, 4))
        self.assertEqual(sig[5], 1)
        self.assertEqual(sig[9], -1)
        self.assertEqual(sig[14], 1)
        self.assertEqual([i for i, s in enumerate(sig) if s], [5, 9, 14])

    def test_short_series_has_no_signals(self):
        self.assertEqual(signals(series([10, 11, 12]), StrategySpec("t", 2, 4)), [0, 0, 0])


if __name__ == "__main__":
    unittest.main()