import unittest
from itertools import islice

from validation.ledger import count
from xauusd_research.schema import iter_candles
from xauusd_research.strategy_generator import generate_and_evaluate

DATA = "data/sample_300k.tsv"


class A4PipelineTests(unittest.TestCase):
    """AT-A4-03 / AT-A4-04."""

    def test_at_a4_03_ten_recorded(self):
        candles = list(islice(iter_candles(DATA), 20000))
        before = count()
        results = generate_and_evaluate(10, seed=11, candles=candles)
        self.assertGreaterEqual(len(results), 5)
        self.assertEqual(count() - before, len(results))

    def test_at_a4_04_verdict_never_none(self):
        candles = list(islice(iter_candles(DATA), 20000))
        for row in generate_and_evaluate(10, seed=13, candles=candles):
            self.assertIn(row["verdict"], {"PASS", "FAIL", "INSUFFICIENT_EVIDENCE"})


if __name__ == "__main__":
    unittest.main()
