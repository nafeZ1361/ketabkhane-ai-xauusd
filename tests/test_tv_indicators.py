"""Tests for TradingView Indicators and Community Catalog."""
from __future__ import annotations
import unittest
from datetime import datetime, timezone
from xauusd_research.schema import Candle
from xauusd_research.indicators.catalog import (
    get_catalog,
    get_verified_indicators,
    get_pending_indicators,
    search_catalog,
)
from xauusd_research.indicators.tv_indicators import (
    calculate_supertrend,
    calculate_squeeze_momentum,
    calculate_halftrend,
    calculate_smc_structure,
    calculate_wavetrend,
    calculate_donchian_channel,
)


def _make_dummy_candles(n: int = 50, trend: float = 1.0) -> list[Candle]:
    base = 2000.0
    candles = []
    for i in range(n):
        open_p = base + i * trend * 0.5
        high_p = open_p + 1.5
        low_p = open_p - 1.2
        close_p = open_p + trend * 0.3
        candles.append(Candle(
            time=datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc),
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=100.0,
        ))
    return candles


class TestTVCatalog(unittest.TestCase):
    def test_catalog_retrieval(self):
        catalog = get_catalog()
        self.assertGreaterEqual(len(catalog), 30)

        verified = get_verified_indicators()
        self.assertGreaterEqual(len(verified), 5)

        pending = get_pending_indicators()
        self.assertGreaterEqual(len(pending), 10)

        # Check key community creators exist
        authors = {item.author for item in catalog}
        for expected in ["LazyBear", "everget", "KivancOzbilgic", "LuxAlgo", "MarketCipher", "ChrisMoody"]:
            self.assertIn(expected, authors)

        # Verify proprietary audit marking
        mc = [item for item in catalog if item.author == "MarketCipher"][0]
        self.assertEqual(mc.status, "UNVERIFIED_PENDING_AUDIT")
        self.assertIn("WaveTrend", mc.description)

    def test_search_catalog(self):
        results = search_catalog("squeeze")
        self.assertTrue(any("LazyBear" in r.author for r in results))

        results_lux = search_catalog("luxalgo")
        self.assertGreaterEqual(len(results_lux), 1)

        empty_search = search_catalog("")
        self.assertEqual(len(empty_search), len(get_catalog()))


class TestTVIndicators(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertEqual(calculate_supertrend([]), [])
        self.assertEqual(calculate_squeeze_momentum([]), [])
        self.assertEqual(calculate_halftrend([]), [])
        self.assertEqual(calculate_smc_structure([]), [])
        self.assertEqual(calculate_wavetrend([]), [])
        self.assertEqual(calculate_donchian_channel([]), [])

    def test_supertrend_bull_and_bear(self):
        candles_bull = _make_dummy_candles(40, trend=1.0)
        st_bull = calculate_supertrend(candles_bull)
        self.assertEqual(len(st_bull), 40)
        self.assertIn(st_bull[-1].trend, [-1, 1])
        self.assertGreater(st_bull[-1].upper_band, 0)
        self.assertGreater(st_bull[-1].lower_band, 0)

        # Non-repainting verification: expanding candles must not alter prior historical values
        st_sub = calculate_supertrend(candles_bull[:30])
        for k in range(30):
            self.assertEqual(st_sub[k].trend, st_bull[k].trend)
            self.assertEqual(st_sub[k].upper_band, st_bull[k].upper_band)
            self.assertEqual(st_sub[k].lower_band, st_bull[k].lower_band)

    def test_squeeze_momentum(self):
        candles = _make_dummy_candles(45, trend=0.2)
        sq = calculate_squeeze_momentum(candles)
        self.assertEqual(len(sq), 45)
        self.assertIsInstance(sq[-1].squeeze_on, bool)
        self.assertIsInstance(sq[-1].momentum, float)
        self.assertIn(sq[-1].signal, [-1, 0, 1])

    def test_halftrend(self):
        candles = _make_dummy_candles(35, trend=-1.0)
        ht = calculate_halftrend(candles)
        self.assertEqual(len(ht), 35)
        self.assertIn(ht[-1].trend, [-1, 1])
        self.assertIsInstance(ht[-1].buy_signal, bool)
        self.assertIsInstance(ht[-1].sell_signal, bool)

    def test_smc_structure(self):
        candles = _make_dummy_candles(40, trend=1.0)
        smc = calculate_smc_structure(candles, swing_length=3)
        self.assertEqual(len(smc), 40)
        self.assertIn(smc[-1].structure, ["NONE", "BOS_BULL", "BOS_BEAR", "CHOCH_BULL", "CHOCH_BEAR"])
        self.assertIn(smc[-1].bias, [-1, 0, 1])

    def test_wavetrend(self):
        candles = _make_dummy_candles(40, trend=0.5)
        wt = calculate_wavetrend(candles)
        self.assertEqual(len(wt), 40)
        self.assertIsInstance(wt[-1].wt1, float)
        self.assertIsInstance(wt[-1].wt2, float)
        self.assertIsInstance(wt[-1].oversold, bool)
        self.assertIsInstance(wt[-1].overbought, bool)

    def test_donchian_channel(self):
        candles = _make_dummy_candles(30, trend=1.0)
        don = calculate_donchian_channel(candles, length=10)
        self.assertEqual(len(don), 30)
        self.assertGreaterEqual(don[-1].upper, don[-1].lower)
        self.assertEqual(don[-1].mid, round((don[-1].upper + don[-1].lower) / 2.0, 4))


if __name__ == "__main__":
    unittest.main()
