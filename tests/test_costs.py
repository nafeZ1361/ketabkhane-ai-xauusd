import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from xauusd_research.backtest import run_backtest
from xauusd_research.costs import (LABEL_PROVISIONAL, LABEL_VERIFIED, BrokerProfile,
                                   UnknownSpecError)
from xauusd_research.schema import Candle
from xauusd_research.strategies import StrategySpec
from xauusd_research.stream import run_stream

BASE = dict(profile_id="t", symbol="XAUUSD", contract_size=100.0, point_size=0.01, tick_size=0.01,
            tick_value=1.0, spread_points=20.0, slippage_points=0.0,
            commission_per_lot_round_turn=7.0, lots=0.1, min_lot=0.01, lot_step=0.01,
            verified=False, source="unit-test")


def series(closes):
    start = datetime(2024, 1, 1)
    return [Candle(start + timedelta(minutes=i), c, c + 0.5, c - 0.5, c) for i, c in enumerate(closes)]


class CostTests(unittest.TestCase):
    def profile(self, **overrides):
        data = dict(BASE)
        data.update(overrides)
        return BrokerProfile.from_dict(data)

    def test_cost_per_trade(self):
        self.assertAlmostEqual(self.profile().cost_per_trade(), 2.7)

    def test_net_pnl(self):
        self.assertAlmostEqual(self.profile().net_pnl(1800.0, 1801.0), 7.3)

    def test_labels(self):
        self.assertEqual(self.profile().label, LABEL_PROVISIONAL)
        self.assertEqual(self.profile(verified=True).label, LABEL_VERIFIED)

    def test_missing_field_is_rejected(self):
        data = dict(BASE)
        data["spread_points"] = None
        with self.assertRaises(UnknownSpecError):
            BrokerProfile.from_dict(data)

    def test_blank_source_is_rejected(self):
        with self.assertRaises(UnknownSpecError):
            self.profile(source="  ")

    def test_lots_below_minimum_is_rejected(self):
        with self.assertRaises(UnknownSpecError):
            self.profile(lots=0.001)

    def test_lots_not_on_step_is_rejected(self):
        with self.assertRaises(UnknownSpecError):
            self.profile(lots=0.105)

    def test_negative_spread_is_rejected(self):
        with self.assertRaises(UnknownSpecError):
            self.profile(spread_points=-1)

    def test_load_from_json(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            path.write_text(json.dumps(BASE), encoding="utf-8")
            self.assertEqual(BrokerProfile.load(path).profile_id, "t")
            with self.assertRaises(UnknownSpecError):
                BrokerProfile.load(Path(tmp) / "missing.json")

    def test_backtest_applies_cost_per_trade(self):
        closes = [10, 10, 10, 10, 10, 11, 12, 13, 12, 11, 10, 9, 8]
        spec = StrategySpec("t", 2, 4)
        candles = series(closes)
        free = run_backtest(candles, spec)
        paid = run_backtest(candles, spec, self.profile())
        self.assertEqual(len(free.trades), len(paid.trades))
        # without a profile pnl is reported in price units; with a profile it is
        # monetary: (exit - entry) * contract_size * lots - cost_per_trade
        self.assertAlmostEqual(free.trades[0].pnl, -2.0)
        self.assertAlmostEqual(paid.trades[0].pnl, -20.0 - 2.7)
        self.assertEqual(paid.label, LABEL_PROVISIONAL)

    def test_stream_matches_batch_with_costs(self):
        closes = [10, 10, 10, 10, 10, 11, 12, 13, 12, 11, 10, 9, 8, 9, 10, 11]
        spec = StrategySpec("t", 2, 4)
        candles = series(closes)
        profile = self.profile()
        self.assertEqual(run_backtest(candles, spec, profile).metrics,
                         run_stream(candles, spec, profile).metrics)


    def test_swap_cost_per_night(self):
        profile = self.profile(swap_daily_pct=0.01, slippage_points=0.0)
        # notional = 4000 * 100 * 0.1 = 40,000 ; 0.01% = 4.0 per night
        self.assertAlmostEqual(profile.swap_cost(4000.0, 3), 12.0)
        self.assertAlmostEqual(profile.swap_cost(4000.0, 0), 0.0)

    def test_net_pnl_includes_swap_for_overnight_trade(self):
        from datetime import datetime
        profile = self.profile(swap_daily_pct=0.01, slippage_points=2.0)
        entry = datetime(2024, 1, 1, 22, 0)
        exit_ = datetime(2024, 1, 4, 2, 0)  # 3 date boundaries
        net = profile.net_pnl(4000.0, 4010.0, entry, exit_)
        gross = 10.0 * 100 * 0.1
        cost = profile.cost_per_trade()
        self.assertAlmostEqual(net, round(gross - cost - 12.0, 6))

    def test_slippage_is_round_trip_points(self):
        profile = self.profile(slippage_points=2.0, spread_points=30.0)
        self.assertAlmostEqual(profile.cost_per_trade(), (30 + 2) * 0.01 * 100 * 0.1 + 7.0 * 0.1)

    def test_example_profile_is_rejected_until_filled(self):
        example = Path(__file__).resolve().parents[1] / "config" / "broker_profile.example.json"
        with self.assertRaises(UnknownSpecError):
            BrokerProfile.load(example)


if __name__ == "__main__":
    unittest.main()