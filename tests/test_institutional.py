import unittest
from datetime import datetime
from xauusd_research.schema import Candle
from xauusd_research.meta_labeling import get_triple_barriers, BarrierEvent
from xauusd_research.regime import calculate_atr, is_major_session
from xauusd_research.fracdiff import get_weights, frac_diff_ffd


class TestInstitutionalEnhancements(unittest.TestCase):
    def setUp(self):
        self.candles = []
        base = 2000.0
        for i in range(100):
            c = Candle(
                time=datetime(2024, 1, 1, 10, i % 60),
                open=base + i * 0.5,
                high=base + i * 0.5 + 1.0,
                low=base + i * 0.5 - 0.5,
                close=base + i * 0.5 + 0.8,
                tickvol=20,
                volume=0,
                spread=30
            )
            self.candles.append(c)

    def test_triple_barriers(self):
        barriers = get_triple_barriers(self.candles, [5, 10, 20], pt_points=100, sl_points=50)
        self.assertEqual(len(barriers), 3)
        self.assertIsInstance(barriers[0], BarrierEvent)
        self.assertIn(barriers[0].barrier_hit, ('profit_take', 'stop_loss', 'time_expiry'))

    def test_regime_and_session(self):
        atr = calculate_atr(self.candles, period=14)
        self.assertIsNotNone(atr[14])
        self.assertTrue(is_major_session(12))
        self.assertFalse(is_major_session(2))

    def test_fracdiff(self):
        weights = get_weights(0.4, 10)
        self.assertEqual(len(weights), 10)
        prices = [c.close for c in self.candles]
        fd = frac_diff_ffd(prices, d=0.4, thres=1e-3)
        self.assertEqual(len(fd), len(prices))
        self.assertIsNotNone(fd[-1])


if __name__ == '__main__':
    unittest.main()
