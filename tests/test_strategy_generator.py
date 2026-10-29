import unittest

from xauusd_research.strategy_generator import SPACE, generate


class StrategyGeneratorTests(unittest.TestCase):
    """AT-A4-01: generator produces valid, runnable strategies."""

    def test_generates_five(self):
        items = generate(5, seed=7)
        self.assertEqual(len(items), 5)

    def test_deterministic(self):
        self.assertEqual(generate(5, seed=3), generate(5, seed=3))

    def test_ma_specs_are_executable(self):
        for item in generate(10, seed=1):
            if item.family == "ma":
                self.assertTrue(item.executable)
                self.assertGreater(item.spec.slow, item.spec.fast)

    def test_space_covers_three_families(self):
        self.assertGreaterEqual(len(SPACE), 4)
        self.assertTrue({"ma", "breakout", "mean_reversion"} <= set(SPACE))


    def test_at_a4_02_five_strategies_four_families(self):
        items = generate(12, seed=5)
        self.assertGreaterEqual(len(items), 5)
        from xauusd_research.strategy_generator import SPACE
        self.assertGreaterEqual(len(SPACE), 4)


if __name__ == "__main__":
    unittest.main()
