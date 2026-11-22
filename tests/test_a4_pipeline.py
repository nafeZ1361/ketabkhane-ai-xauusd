"""A4 pipeline tests use deterministic synthetic candles, never local market data."""

import math
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from validation.ledger import count
from xauusd_research.schema import iter_candles
from xauusd_research.strategy_generator import generate_and_evaluate


def _write_synthetic_data(path: Path, rows: int = 1200) -> Path:
    """Create a small deterministic TSV fixture for generator/backtest integration."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["DATE\tTIME\tOPEN\tHIGH\tLOW\tCLOSE\tTICKVOL"]
    start = datetime(2024, 1, 2)  # winter date: avoids ambiguous EU DST wall times
    for i in range(rows):
        stamp = start + timedelta(minutes=i)
        close = 2000.0 + (i * 0.0005) + 1.5 * math.sin(i / 23.0)
        open_price = close + 0.04 * math.cos(i / 11.0)
        high = max(open_price, close) + 0.10
        low = min(open_price, close) - 0.10
        lines.append(
            f"{stamp:%Y.%m.%d}\t{stamp:%H:%M:%S}\t"
            f"{open_price:.5f}\t{high:.5f}\t{low:.5f}\t{close:.5f}\t{100 + i % 17}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class A4PipelineTests(unittest.TestCase):
    """AT-A4-03 / AT-A4-04."""

    def _candles(self):
        with tempfile.TemporaryDirectory(prefix="a4-pipeline-") as directory:
            path = _write_synthetic_data(Path(directory) / "a4_sample.tsv")
            return list(iter_candles(path))

    def test_at_a4_03_ten_recorded(self):
        candles = self._candles()
        before = count()
        results = generate_and_evaluate(10, seed=11, candles=candles)
        self.assertGreaterEqual(len(results), 5)
        self.assertEqual(count() - before, len(results))

    def test_at_a4_04_verdict_never_none(self):
        candles = self._candles()
        for row in generate_and_evaluate(10, seed=13, candles=candles):
            self.assertIn(row["verdict"], {"PASS", "FAIL", "INSUFFICIENT_EVIDENCE"})


if __name__ == "__main__":
    unittest.main()
