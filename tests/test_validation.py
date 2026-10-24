import unittest
from datetime import datetime, timedelta

from xauusd_research.schema import Candle
from xauusd_research.validation import validate


def candle(minute, o=10.0, h=11.0, l=9.0, c=10.5):
    return Candle(datetime(2024, 1, 1) + timedelta(minutes=minute), o, h, l, c)


class ValidationTests(unittest.TestCase):
    def test_clean_series(self):
        report = validate([candle(i) for i in range(5)])
        self.assertFalse(report.fatal)
        self.assertEqual(report.issues, [])
        self.assertEqual(report.rows, 5)

    def test_empty_series_is_fatal(self):
        report = validate([])
        self.assertTrue(report.fatal)
        self.assertEqual(report.codes(), ["EMPTY"])

    def test_duplicate_timestamp_is_fatal(self):
        report = validate([candle(0), candle(0)])
        self.assertTrue(report.fatal)
        self.assertIn("DUPLICATE_TIME", report.codes())

    def test_out_of_order_is_fatal(self):
        report = validate([candle(5), candle(1)])
        self.assertTrue(report.fatal)
        self.assertIn("OUT_OF_ORDER", report.codes())

    def test_bad_ohlc_is_fatal(self):
        report = validate([candle(0, o=10, h=9.5, l=9, c=10)])
        self.assertTrue(report.fatal)
        self.assertIn("BAD_OHLC", report.codes())

    def test_non_positive_price_is_fatal(self):
        report = validate([candle(0, o=0, h=1, l=0, c=0.5)])
        self.assertTrue(report.fatal)
        self.assertIn("NON_POSITIVE_PRICE", report.codes())

    def test_gaps_are_counted(self):
        series = [candle(0), candle(1), candle(2), candle(30), candle(31)]
        self.assertEqual(validate(series).gaps, 1)

    def test_gap_is_not_fatal(self):
        series = [candle(0), candle(1), candle(30)]
        self.assertFalse(validate(series).fatal)


if __name__ == "__main__":
    unittest.main()