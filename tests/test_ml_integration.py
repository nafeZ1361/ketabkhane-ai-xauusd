import unittest
from datetime import datetime, timedelta

from xauusd_research.fracdiff import frac_diff_ffd, get_weights
from xauusd_research.meta_labeling import get_triple_barriers
from xauusd_research.regime import calculate_atr, is_major_session
from xauusd_research.schema import Candle


def series(n=200, step=1.0):
    start = datetime(2024, 1, 1)
    out, price = [], 1800.0
    for i in range(n):
        price += step
        out.append(Candle(start + timedelta(minutes=i), price, price + 1, price - 1, price))
    return out


class MlIntegrationTests(unittest.TestCase):
    """AT-ML-01: fracdiff -> regime -> meta-labeling on one series."""

    def test_fracdiff_weights_sum_to_one(self):
        weights = get_weights(0.4, 10)
        self.assertEqual(len(weights), 10)
        self.assertAlmostEqual(weights[0], 1.0, places=6)

    def test_fracdiff_output_shape(self):
        out = frac_diff_ffd([float(i) for i in range(120)], 0.4)
        self.assertEqual(len(out), 120)
        self.assertTrue(any(v is not None for v in out))

    def test_regime_atr_positive(self):
        candles = series()
        atr = calculate_atr(candles, period=14)
        self.assertEqual(len(atr), len(candles))
        self.assertGreater(max(v for v in atr if v is not None), 0)
        self.assertTrue(is_major_session(10))
        self.assertFalse(is_major_session(3))

    def test_triple_barrier_labels(self):
        candles = series()
        labels = get_triple_barriers(candles, [10, 50, 100], pt_points=150, sl_points=100, max_holding_bars=50)
        self.assertEqual(len(labels), 3)
        for event in labels:
            self.assertIn(event.label, (-1, 0, 1))


if __name__ == "__main__":
    unittest.main()
