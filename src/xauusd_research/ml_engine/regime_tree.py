"""Machine Learning Regime Classifier and Decision Tree for XAUUSD.

Classifies market state into:
- BULL_TREND
- BEAR_TREND
- CHOPPY_RANGE
- VOLATILITY_SHOCK

Provides probabilistic confidence, risk multipliers, and strategy gating.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence
from xauusd_research.schema import Candle


class MarketRegime(str, Enum):
    BULL_TREND = "BULL_TREND"
    BEAR_TREND = "BEAR_TREND"
    CHOPPY_RANGE = "CHOPPY_RANGE"
    VOLATILITY_SHOCK = "VOLATILITY_SHOCK"


@dataclass(frozen=True)
class RegimeFeatures:
    volatility_ratio: float  # Current 14-period ATR / 50-period ATR
    slope_norm: float        # Normalized price slope over 20 bars
    range_compression: float # (Highest - Lowest) / ATR
    autocorr_lag1: float     # 1-lag return autocorrelation (-1 to +1)


@dataclass(frozen=True)
class RegimeClassification:
    regime: MarketRegime
    confidence: float        # 0.0 to 1.0
    risk_multiplier: float   # Recommended position sizing factor (e.g. 0.0 in shock, 1.0 in clean trend)
    action_gate: str         # "ALLOW_TREND" | "ALLOW_RANGE" | "RESTRICT_SIZE" | "CASH_LOCKOUT"
    features: RegimeFeatures


class RegimeDecisionEngine:
    """Decision Tree based Regime Classifier calibrated on empirical gold market dynamics."""

    def __init__(
        self,
        shock_vol_threshold: float = 1.85,
        trend_slope_threshold: float = 0.0015,
        chop_autocorr_threshold: float = -0.15,
    ) -> None:
        self.shock_vol_threshold = shock_vol_threshold
        self.trend_slope_threshold = trend_slope_threshold
        self.chop_autocorr_threshold = chop_autocorr_threshold

    def extract_features(self, candles: Sequence[Candle], index: int) -> RegimeFeatures:
        if index < 20 or not candles:
            return RegimeFeatures(1.0, 0.0, 1.0, 0.0)

        # 1. Volatility ratio (short vs long ATR)
        sub_short = candles[max(0, index - 14): index + 1]
        sub_long = candles[max(0, index - 50): index + 1]

        tr_short = sum(c.high - c.low for c in sub_short) / max(1, len(sub_short))
        tr_long = sum(c.high - c.low for c in sub_long) / max(1, len(sub_long))
        vol_ratio = tr_short / tr_long if tr_long > 0 else 1.0

        # 2. Normalized slope over 20 bars
        window = candles[max(0, index - 20): index + 1]
        n = len(window)
        closes = [c.close for c in window]
        mean_p = sum(closes) / n
        if n >= 2 and mean_p > 0:
            sum_x = n * (n - 1) / 2.0
            sum_xx = n * (n - 1) * (2 * n - 1) / 6.0
            sum_y = sum(closes)
            sum_xy = sum(i * closes[i] for i in range(n))
            denom = (n * sum_xx - sum_x * sum_x)
            slope = (n * sum_xy - sum_x * sum_y) / denom if abs(denom) > 1e-12 else 0.0
            slope_norm = slope / mean_p
        else:
            slope_norm = 0.0

        # 3. Range compression
        highest = max(c.high for c in window)
        lowest = min(c.low for c in window)
        range_span = highest - lowest
        range_comp = range_span / tr_short if tr_short > 0 else 1.0

        # 4. Return autocorrelation (lag-1)
        returns = [
            (window[k].close - window[k - 1].close) / window[k - 1].close
            for k in range(1, n)
            if window[k - 1].close > 0
        ]
        if len(returns) >= 5:
            mean_r = sum(returns) / len(returns)
            devs = [r - mean_r for r in returns]
            var = sum(d * d for d in devs)
            if var > 1e-12:
                cov = sum(devs[k] * devs[k - 1] for k in range(1, len(devs)))
                autocorr = cov / var
            else:
                autocorr = 0.0
        else:
            autocorr = 0.0

        return RegimeFeatures(
            volatility_ratio=round(vol_ratio, 4),
            slope_norm=round(slope_norm, 6),
            range_compression=round(range_comp, 4),
            autocorr_lag1=round(autocorr, 4),
        )

    def classify(self, features: RegimeFeatures) -> RegimeClassification:
        # Node 1: Volatility Shock check (High risk flash event / NFP / CPI)
        if features.volatility_ratio >= self.shock_vol_threshold:
            conf = min(0.99, 0.70 + (features.volatility_ratio - self.shock_vol_threshold) * 0.2)
            return RegimeClassification(
                regime=MarketRegime.VOLATILITY_SHOCK,
                confidence=round(conf, 3),
                risk_multiplier=0.0,
                action_gate="CASH_LOCKOUT",
                features=features,
            )

        # Node 2: Directional Trend branches
        if features.slope_norm > self.trend_slope_threshold:
            conf = min(0.95, 0.65 + abs(features.slope_norm) * 50.0)
            return RegimeClassification(
                regime=MarketRegime.BULL_TREND,
                confidence=round(conf, 3),
                risk_multiplier=1.0,
                action_gate="ALLOW_TREND",
                features=features,
            )
        elif features.slope_norm < -self.trend_slope_threshold:
            conf = min(0.95, 0.65 + abs(features.slope_norm) * 50.0)
            return RegimeClassification(
                regime=MarketRegime.BEAR_TREND,
                confidence=round(conf, 3),
                risk_multiplier=1.0,
                action_gate="ALLOW_TREND",
                features=features,
            )

        # Node 3: Choppy / Mean-Reverting Range
        conf = 0.75 if features.autocorr_lag1 < self.chop_autocorr_threshold else 0.60
        return RegimeClassification(
            regime=MarketRegime.CHOPPY_RANGE,
            confidence=round(conf, 3),
            risk_multiplier=0.4,
            action_gate="ALLOW_RANGE",
            features=features,
        )

    def evaluate_series(self, candles: Sequence[Candle]) -> list[RegimeClassification]:
        """Classifies each candle sequentially with non-repainting historical memory."""
        results: list[RegimeClassification] = []
        for i in range(len(candles)):
            feat = self.extract_features(candles, i)
            clf = self.classify(feat)
            results.append(clf)
        return results
