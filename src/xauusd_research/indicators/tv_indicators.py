"""Pure Python, zero-dependency implementations of TradingView quantitative indicators.

Designed with non-repainting next-bar execution guarantees:
Each bar $t$ output depends exclusively on bars $0 ... t$.
Signals generated at the close of bar $t$ are meant for execution at the open of bar $t+1$.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Sequence
from xauusd_research.schema import Candle


@dataclass(frozen=True)
class SupertrendResult:
    upper_band: float
    lower_band: float
    trend: int  # 1 = Bullish, -1 = Bearish
    signal: int  # 1 = Bullish flip on bar close, -1 = Bearish flip, 0 = Hold


@dataclass(frozen=True)
class SqueezeResult:
    squeeze_on: bool
    momentum: float
    momentum_increasing: bool
    signal: int  # 1 = Bull breakout, -1 = Bear breakout, 0 = None


@dataclass(frozen=True)
class HalfTrendResult:
    trend_line: float
    trend: int  # 1 = Bullish, -1 = Bearish
    buy_signal: bool
    sell_signal: bool


@dataclass(frozen=True)
class SMCStructureResult:
    swing_high: float | None
    swing_low: float | None
    structure: str  # "NONE" | "BOS_BULL" | "BOS_BEAR" | "CHOCH_BULL" | "CHOCH_BEAR"
    bias: int  # 1 = Bullish, -1 = Bearish, 0 = Neutral


@dataclass(frozen=True)
class WaveTrendResult:
    wt1: float
    wt2: float
    oversold: bool
    overbought: bool
    bull_cross: bool
    bear_cross: bool


@dataclass(frozen=True)
class DonchianResult:
    upper: float
    lower: float
    mid: float
    breakout_bull: bool
    breakout_bear: bool


def _calculate_tr(candles: Sequence[Candle]) -> list[float]:
    tr = []
    for i, c in enumerate(candles):
        if i == 0:
            tr.append(c.high - c.low)
        else:
            prev_close = candles[i - 1].close
            tr.append(max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close)))
    return tr


def _rma(values: Sequence[float], length: int) -> list[float]:
    """Wilders smoothing / RMA used by Pine Script ATR."""
    if not values:
        return []
    alpha = 1.0 / length
    res = [0.0] * len(values)
    # initial SMA
    if len(values) < length:
        # fallback simple average
        run_sum = sum(values)
        return [run_sum / len(values)] * len(values)
    initial_sum = sum(values[:length])
    res[length - 1] = initial_sum / length
    for i in range(length):
        res[i] = initial_sum / length
    for i in range(length, len(values)):
        res[i] = alpha * values[i] + (1.0 - alpha) * res[i - 1]
    return res


def _ema(values: Sequence[float], length: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (length + 1)
    res = [values[0]] * len(values)
    for i in range(1, len(values)):
        res[i] = alpha * values[i] + (1.0 - alpha) * res[i - 1]
    return res


def _sma(values: Sequence[float], length: int) -> list[float]:
    if not values:
        return []
    res = [0.0] * len(values)
    running_sum = 0.0
    for i, val in enumerate(values):
        running_sum += val
        if i >= length:
            running_sum -= values[i - length]
            res[i] = running_sum / length
        else:
            res[i] = running_sum / (i + 1)
    return res


def _linreg_slope_intercept(values: Sequence[float]) -> float:
    """Linear regression end value (slope * (n-1) + intercept) over window."""
    n = len(values)
    if n < 2:
        return values[-1] if values else 0.0
    sum_x = n * (n - 1) / 2.0
    sum_y = sum(values)
    sum_xx = n * (n - 1) * (2 * n - 1) / 6.0
    sum_xy = sum(i * values[i] for i in range(n))
    denominator = (n * sum_xx - sum_x * sum_x)
    if abs(denominator) < 1e-12:
        return sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n
    return slope * (n - 1) + intercept


def calculate_supertrend(
    candles: Sequence[Candle],
    period: int = 10,
    multiplier: float = 3.0,
) -> list[SupertrendResult]:
    """Calculates Supertrend (everget / KivancOzbilgic) with strict non-repainting."""
    n = len(candles)
    if n == 0:
        return []
    tr = _calculate_tr(candles)
    atr = _rma(tr, period)

    results: list[SupertrendResult] = []
    final_upper = 0.0
    final_lower = 0.0
    trend = 1

    for i in range(n):
        c = candles[i]
        hl2 = (c.high + c.low) / 2.0
        cur_atr = atr[i] if i < len(atr) else 0.0
        basic_upper = hl2 + multiplier * cur_atr
        basic_lower = hl2 - multiplier * cur_atr

        if i == 0:
            final_upper = basic_upper
            final_lower = basic_lower
            trend = 1
            results.append(SupertrendResult(final_upper, final_lower, trend, 0))
            continue

        prev_close = candles[i - 1].close

        # Upper band ratchet
        if basic_upper < final_upper or prev_close > final_upper:
            final_upper = basic_upper
        # Lower band ratchet
        if basic_lower > final_lower or prev_close < final_lower:
            final_lower = basic_lower

        prev_trend = trend
        signal = 0

        if prev_trend == 1:
            if c.close < final_lower:
                trend = -1
                signal = -1
            else:
                trend = 1
        else:
            if c.close > final_upper:
                trend = 1
                signal = 1
            else:
                trend = -1

        results.append(SupertrendResult(
            upper_band=round(final_upper, 4),
            lower_band=round(final_lower, 4),
            trend=trend,
            signal=signal,
        ))
    return results


def calculate_squeeze_momentum(
    candles: Sequence[Candle],
    bb_length: int = 20,
    bb_mult: float = 2.0,
    kc_length: int = 20,
    kc_mult: float = 1.5,
) -> list[SqueezeResult]:
    """Calculates LazyBear Squeeze Momentum Indicator."""
    n = len(candles)
    if n == 0:
        return []
    closes = [c.close for c in candles]
    tr = _calculate_tr(candles)

    sma_bb = _sma(closes, bb_length)
    sma_kc = _sma(closes, kc_length)
    atr_kc = _sma(tr, kc_length)

    results: list[SqueezeResult] = []
    for i in range(n):
        window_bb = closes[max(0, i - bb_length + 1): i + 1]
        mean_bb = sma_bb[i]
        variance = sum((x - mean_bb) ** 2 for x in window_bb) / max(1, len(window_bb))
        std_bb = math.sqrt(variance)

        bb_upper = mean_bb + bb_mult * std_bb
        bb_lower = mean_bb - bb_mult * std_bb

        kc_upper = sma_kc[i] + kc_mult * atr_kc[i]
        kc_lower = sma_kc[i] - kc_mult * atr_kc[i]

        squeeze_on = (bb_lower > kc_lower) and (bb_upper < kc_upper)

        # Linear regression momentum
        # average of highest high and lowest low + sma
        sub_candles = candles[max(0, i - kc_length + 1): i + 1]
        highest_h = max(sc.high for sc in sub_candles)
        lowest_l = min(sc.low for sc in sub_candles)
        mid_val = ((highest_h + lowest_l) / 2.0 + sma_kc[i]) / 2.0

        # delta array for linear regression over last kc_length bars
        delta_window = []
        for j in range(max(0, i - kc_length + 1), i + 1):
            delta_window.append(closes[j] - mid_val)

        mom = _linreg_slope_intercept(delta_window)

        mom_inc = True
        if results:
            prev_mom = results[-1].momentum
            mom_inc = mom >= prev_mom

        signal = 0
        if results and results[-1].squeeze_on and not squeeze_on:
            signal = 1 if mom > 0 else -1

        results.append(SqueezeResult(
            squeeze_on=squeeze_on,
            momentum=round(mom, 4),
            momentum_increasing=mom_inc,
            signal=signal,
        ))
    return results


def calculate_halftrend(
    candles: Sequence[Candle],
    amplitude: int = 2,
    channel_deviation: float = 2.0,
) -> list[HalfTrendResult]:
    """Calculates Alex Orekhov / everget HalfTrend."""
    n = len(candles)
    if n == 0:
        return []
    tr = _calculate_tr(candles)
    atr = _sma(tr, 100)

    results: list[HalfTrendResult] = []
    trend = 0
    next_trend = 0
    max_low = candles[0].low
    min_high = candles[0].high
    trend_line = (candles[0].high + candles[0].low) / 2.0

    for i in range(n):
        c = candles[i]
        cur_atr = atr[i] / 2.0 if atr[i] > 0 else 1.0
        dev = channel_deviation * cur_atr

        sub_candles = candles[max(0, i - amplitude + 1): i + 1]
        highest = max(sc.high for sc in sub_candles)
        lowest = min(sc.low for sc in sub_candles)

        if next_trend == 1:
            max_low = max(lowest, max_low)
            if (min_high < highest) and (c.close < lowest):
                trend = 0
                next_trend = 0
                min_high = highest
        else:
            min_high = min(highest, min_high)
            if (max_low > lowest) and (c.close > highest):
                trend = 1
                next_trend = 1
                max_low = lowest

        buy_signal = False
        sell_signal = False
        if trend == 1:
            trend_line = max_low
            if results and results[-1].trend == -1:
                buy_signal = True
        else:
            trend_line = min_high
            if results and results[-1].trend == 1:
                sell_signal = True

        out_trend = 1 if trend == 1 else -1
        results.append(HalfTrendResult(
            trend_line=round(trend_line, 4),
            trend=out_trend,
            buy_signal=buy_signal,
            sell_signal=sell_signal,
        ))
    return results


def calculate_smc_structure(
    candles: Sequence[Candle],
    swing_length: int = 5,
) -> list[SMCStructureResult]:
    """Calculates LuxAlgo / Smart Money Concepts swing high/low structure and BOS/CHoCH."""
    n = len(candles)
    if n == 0:
        return []

    results: list[SMCStructureResult] = []
    active_sh: float | None = None
    active_sl: float | None = None
    prior_bias = 0

    for i in range(n):
        # A swing point is verified strictly when swing_length bars have passed after the peak
        if i >= 2 * swing_length:
            center_idx = i - swing_length
            center_high = candles[center_idx].high
            center_low = candles[center_idx].low

            # Check if center_idx was swing high
            is_sh = all(
                center_high >= candles[k].high
                for k in range(center_idx - swing_length, center_idx + swing_length + 1)
            )
            if is_sh:
                active_sh = center_high

            # Check if center_idx was swing low
            is_sl = all(
                center_low <= candles[k].low
                for k in range(center_idx - swing_length, center_idx + swing_length + 1)
            )
            if is_sl:
                active_sl = center_low

        c = candles[i]
        structure = "NONE"
        bias = prior_bias

        if active_sh is not None and c.close > active_sh:
            if prior_bias == -1:
                structure = "CHOCH_BULL"
            else:
                structure = "BOS_BULL"
            bias = 1
            active_sh = None  # Swept

        elif active_sl is not None and c.close < active_sl:
            if prior_bias == 1:
                structure = "CHOCH_BEAR"
            else:
                structure = "BOS_BEAR"
            bias = -1
            active_sl = None  # Swept

        prior_bias = bias
        results.append(SMCStructureResult(
            swing_high=round(active_sh, 4) if active_sh else None,
            swing_low=round(active_sl, 4) if active_sl else None,
            structure=structure,
            bias=bias,
        ))
    return results


def calculate_wavetrend(
    candles: Sequence[Candle],
    n1: int = 10,
    n2: int = 21,
) -> list[WaveTrendResult]:
    """Calculates LazyBear WaveTrend (Cipher B basis oscillator)."""
    n = len(candles)
    if n == 0:
        return []

    ap = [(c.high + c.low + c.close) / 3.0 for c in candles]
    esa = _ema(ap, n1)
    diff = [abs(ap[i] - esa[i]) for i in range(n)]
    d = _ema(diff, n1)

    ci = [0.0] * n
    for i in range(n):
        if d[i] > 1e-6:
            ci[i] = (ap[i] - esa[i]) / (0.015 * d[i])
        else:
            ci[i] = 0.0

    wt1 = _ema(ci, n2)
    wt2 = _sma(wt1, 4)

    results: list[WaveTrendResult] = []
    for i in range(n):
        w1 = wt1[i]
        w2 = wt2[i]
        os = w1 <= -53.0
        ob = w1 >= 53.0

        bull_cross = False
        bear_cross = False
        if i > 0:
            prev_w1 = wt1[i - 1]
            prev_w2 = wt2[i - 1]
            if prev_w1 <= prev_w2 and w1 > w2:
                bull_cross = True
            elif prev_w1 >= prev_w2 and w1 < w2:
                bear_cross = True

        results.append(WaveTrendResult(
            wt1=round(w1, 2),
            wt2=round(w2, 2),
            oversold=os,
            overbought=ob,
            bull_cross=bull_cross,
            bear_cross=bear_cross,
        ))
    return results


def calculate_donchian_channel(
    candles: Sequence[Candle],
    length: int = 20,
) -> list[DonchianResult]:
    """Calculates Donchian Channel High/Low and breakout signals."""
    n = len(candles)
    if n == 0:
        return []

    results: list[DonchianResult] = []
    for i in range(n):
        start_idx = max(0, i - length)
        sub = candles[start_idx:i]  # strictly preceding bars for non-repainting breakout
        if not sub:
            high_bound = candles[i].high
            low_bound = candles[i].low
        else:
            high_bound = max(c.high for c in sub)
            low_bound = min(c.low for c in sub)

        mid = (high_bound + low_bound) / 2.0
        cur_c = candles[i].close

        results.append(DonchianResult(
            upper=round(high_bound, 4),
            lower=round(low_bound, 4),
            mid=round(mid, 4),
            breakout_bull=cur_c > high_bound,
            breakout_bear=cur_c < low_bound,
        ))
    return results
