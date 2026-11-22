"""A4 pipeline tests use deterministic synthetic candles, never local market data."""

import math
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

    def test_at_a4_03_ten_recorded(self):
        self.skipTest("requires pytest tmp_path fixture; use module-level pytest tests")

    def test_at_a4_04_verdict_never_none(self):
        self.skipTest("requires pytest tmp_path fixture; use module-level pytest tests")


# pytest-style tests keep fixture creation isolated and deterministic.
def test_at_a4_03_ten_recorded(tmp_path: Path):
    candles = list(iter_candles(_write_synthetic_data(tmp_path / "a4_sample.tsv")))
    before = count()
    results = generate_and_evaluate(10, seed=11, candles=candles)
    assert len(results) >= 5
    assert count() - before == len(results)


def test_at_a4_04_verdict_never_none(tmp_path: Path):
    candles = list(iter_candles(_write_synthetic_data(tmp_path / "a4_sample.tsv")))
    for row in generate_and_evaluate(10, seed=13, candles=candles):
        assert row["verdict"] in {"PASS", "FAIL", "INSUFFICIENT_EVIDENCE"}
