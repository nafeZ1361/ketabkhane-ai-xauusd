import random
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from xauusd_research.backtest import run_backtest
from xauusd_research.schema import Candle, iter_candles, load_candles
from xauusd_research.strategies import STRATEGY_BY_NAME, StrategySpec
from xauusd_research.stream import StreamingBacktester, run_stream
from xauusd_research.validation import StreamingValidator, validate

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "synthetic_500.csv"


def series(closes):
    start = datetime(2024, 1, 1)
    return [Candle(start + timedelta(minutes=i), c, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]


class StreamTests(unittest.TestCase):
    def test_matches_batch_on_fixture(self):
        for name in ("ma_5_20", "ma_10_50", "ma_20_100"):
            spec = STRATEGY_BY_NAME[name]
            batch = run_backtest(load_candles(FIXTURE), spec)
            streamed = run_stream(iter_candles(FIXTURE), spec)
            self.assertEqual(len(batch.trades), len(streamed.trades), name)
            self.assertEqual(batch.metrics, streamed.metrics, name)
            for a, b in zip(batch.trades, streamed.trades):
                self.assertEqual((a.entry_time, a.exit_time, a.pnl), (b.entry_time, b.exit_time, b.pnl))

    def test_matches_batch_on_random_walk(self):
        rng = random.Random(7)
        price, closes = 1800.0, []
        for _ in range(2000):
            price += rng.uniform(-1.5, 1.5)
            closes.append(round(price, 2))
        candles = series(closes)
        spec = StrategySpec("t", 5, 20)
        batch = run_backtest(candles, spec)
        streamed = run_stream(candles, spec)
        self.assertGreater(len(batch.trades), 5)
        self.assertEqual(batch.metrics, streamed.metrics)

    def test_empty_stream(self):
        engine = StreamingBacktester(StrategySpec("t", 2, 4))
        result = engine.finish()
        self.assertEqual(result.trades, [])
        self.assertEqual(StreamingValidator().report().codes(), ["EMPTY"])

    def test_streaming_validator_matches_batch(self):
        candles = series([10, 11, 12, 13, 14, 13, 12])
        self.assertEqual(validate(candles).gaps, StreamingValidator().report().gaps)
        validator = StreamingValidator()
        for candle in candles:
            validator.feed(candle)
        self.assertEqual(validator.report().rows, len(candles))
        self.assertFalse(validator.report().fatal)


if __name__ == "__main__":
    unittest.main()