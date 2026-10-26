"""Tests for Machine Learning Regime Classification and Feedback Loop."""
from __future__ import annotations
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from xauusd_research.schema import Candle
from xauusd_research.ml_engine.regime_tree import (
    MarketRegime,
    RegimeDecisionEngine,
    RegimeFeatures,
)
from xauusd_research.ml_engine.feedback_loop import (
    AdaptiveFeedbackLoop,
    FeedbackLedger,
    TradeOutcomeDiagnosis,
    TradeRecord,
)


def _make_dummy_candles(n: int = 60, step: float = 0.5, shock_at: int | None = None) -> list[Candle]:
    base = 2050.0
    candles = []
    for i in range(n):
        open_p = base + i * step
        high_p = open_p + 1.2
        low_p = open_p - 1.0
        close_p = open_p + step * 0.8
        if shock_at is not None and i == shock_at:
            high_p = open_p + 35.0
            low_p = open_p - 35.0
        candles.append(Candle(
            time=datetime(2026, 1, 1, 0, i, tzinfo=timezone.utc),
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=150.0,
        ))
    return candles


class TestMLRegime(unittest.TestCase):
    def test_feature_extraction_and_classification(self):
        engine = RegimeDecisionEngine()
        candles = _make_dummy_candles(60, step=0.8)

        # Baseline feature extraction
        feats = engine.extract_features(candles, 40)
        self.assertIsInstance(feats.volatility_ratio, float)
        self.assertIsInstance(feats.slope_norm, float)

        clf = engine.classify(feats)
        self.assertIn(clf.regime, [MarketRegime.BULL_TREND, MarketRegime.BEAR_TREND, MarketRegime.CHOPPY_RANGE, MarketRegime.VOLATILITY_SHOCK])
        self.assertGreater(clf.confidence, 0.0)

    def test_shock_detection(self):
        engine = RegimeDecisionEngine()
        shock_candles = _make_dummy_candles(60, step=0.1, shock_at=55)
        feats = engine.extract_features(shock_candles, 55)
        clf = engine.classify(feats)
        self.assertEqual(clf.regime, MarketRegime.VOLATILITY_SHOCK)
        self.assertEqual(clf.risk_multiplier, 0.0)
        self.assertEqual(clf.action_gate, "CASH_LOCKOUT")

    def test_series_evaluation(self):
        engine = RegimeDecisionEngine()
        candles = _make_dummy_candles(30, step=0.5)
        series = engine.evaluate_series(candles)
        self.assertEqual(len(series), 30)


class TestFeedbackLoop(unittest.TestCase):
    def test_ledger_and_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file = Path(tmpdir) / "test_feedback.jsonl"
            ledger = FeedbackLedger(ledger_path=ledger_file)

            diag = TradeOutcomeDiagnosis(
                trade_id="TR-001",
                pnl=12.5,
                error_category="NONE",
                root_cause="Clean execution.",
                adaptive_recommendation="MAINTAIN_CURRENT_WEIGHTS",
            )
            ledger.record(diag)

            self.assertTrue(ledger_file.exists())
            self.assertEqual(len(ledger.diagnoses), 1)
            stats = ledger.summary_stats()
            self.assertEqual(stats["total_trades"], 1)
            self.assertEqual(stats["error_breakdown"]["NONE"], 1)

    def test_adaptive_diagnosis_and_tuning(self):
        ledger = FeedbackLedger()
        loop = AdaptiveFeedbackLoop(ledger=ledger)

        # 1. Winning trade
        t_win = TradeRecord(
            trade_id="T1", entry_time="08:00", exit_time="09:00",
            direction=1, entry_price=2000.0, exit_price=2010.0,
            pnl=10.0, gross_pnl=10.2, costs=0.2,
            entry_regime=MarketRegime.BULL_TREND, exit_regime=MarketRegime.BULL_TREND,
            bars_held=10,
        )
        d_win = loop.diagnose_trade(t_win)
        self.assertEqual(d_win.error_category, "NONE")

        # 2. Chop whipsaw
        t_chop = TradeRecord(
            trade_id="T2", entry_time="10:00", exit_time="10:30",
            direction=1, entry_price=2005.0, exit_price=2001.0,
            pnl=-4.0, gross_pnl=-3.8, costs=0.2,
            entry_regime=MarketRegime.CHOPPY_RANGE, exit_regime=MarketRegime.CHOPPY_RANGE,
            bars_held=5,
        )
        d_chop = loop.diagnose_trade(t_chop)
        self.assertEqual(d_chop.error_category, "CHOP_WHIPSAW")

        # 3. Volatility shock loss
        t_shock = TradeRecord(
            trade_id="T3", entry_time="13:00", exit_time="13:10",
            direction=-1, entry_price=2000.0, exit_price=2020.0,
            pnl=-20.0, gross_pnl=-19.8, costs=0.2,
            entry_regime=MarketRegime.VOLATILITY_SHOCK, exit_regime=MarketRegime.VOLATILITY_SHOCK,
            bars_held=3,
        )
        d_shock = loop.diagnose_trade(t_shock)
        self.assertEqual(d_shock.error_category, "VOL_SHOCK_LOSS")

        # 4. Premature exit
        t_premature = TradeRecord(
            trade_id="T4", entry_time="14:00", exit_time="14:02",
            direction=1, entry_price=2000.0, exit_price=1998.0,
            pnl=-2.0, gross_pnl=-1.8, costs=0.2,
            entry_regime=MarketRegime.BULL_TREND, exit_regime=MarketRegime.BULL_TREND,
            bars_held=1,
        )
        d_pre = loop.diagnose_trade(t_premature)
        self.assertEqual(d_pre.error_category, "PREMATURE_EXIT")

        # 5. Spread overrun
        t_spread = TradeRecord(
            trade_id="T5", entry_time="15:00", exit_time="15:20",
            direction=1, entry_price=2000.0, exit_price=2000.1,
            pnl=-0.3, gross_pnl=0.1, costs=0.4,
            entry_regime=MarketRegime.BULL_TREND, exit_regime=MarketRegime.BULL_TREND,
            bars_held=6,
        )
        d_spread = loop.diagnose_trade(t_spread)
        self.assertEqual(d_spread.error_category, "SPREAD_OVERRUN")

        # Parameter adaptation check
        orig_conf = loop.params.min_trend_confidence
        adapted_params = loop.adapt_parameters()
        self.assertGreaterEqual(adapted_params.min_trend_confidence, orig_conf)
        self.assertTrue(adapted_params.lockout_in_shock)


if __name__ == "__main__":
    unittest.main()
