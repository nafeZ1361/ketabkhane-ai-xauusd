"""TradingView & Community Creator Indicator Registry.

Maintains verified catalog of community creators, firms, and algorithms.
Distinguishes between mathematically verified open-source indicators and
unverified / proprietary closed scripts requiring audit.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class IndicatorMeta:
    id: str
    author: str
    name: str
    item_type: str  # 'indicator' | 'strategy' | 'ml_model'
    status: str     # 'VERIFIED_IMPLEMENTED' | 'UNVERIFIED_PENDING_AUDIT'
    repainting_risk: str  # 'NONE' | 'LOW' | 'HIGH_IF_MTF_UNCONFIRMED'
    description: str
    pine_reference: str
    implementation_fn: Optional[str] = None


INDICATOR_CATALOG: list[IndicatorMeta] = [
    # --- Verified Open Community Creators ---
    IndicatorMeta(
        id="tv_everget_supertrend",
        author="everget",
        name="Supertrend Indicator",
        item_type="indicator",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="True Range trailing volatility band that switches trend on bar close breakout.",
        pine_reference="TradingView: everget/supertrend",
        implementation_fn="calculate_supertrend",
    ),
    IndicatorMeta(
        id="tv_kivanc_alphatrend",
        author="KivancOzbilgic",
        name="AlphaTrend / Supertrend Suite",
        item_type="indicator",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="Momentum-filtered adaptive ATR trailing stop with MFI and RSI bias.",
        pine_reference="TradingView: KivancOzbilgic/AlphaTrend",
        implementation_fn="calculate_supertrend",
    ),
    IndicatorMeta(
        id="tv_lazybear_squeeze",
        author="LazyBear",
        name="Squeeze Momentum Indicator",
        item_type="indicator",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="Bollinger Band compression inside Keltner Channel with linear regression momentum.",
        pine_reference="TradingView: LazyBear/Squeeze-Momentum-Indicator",
        implementation_fn="calculate_squeeze_momentum",
    ),
    IndicatorMeta(
        id="tv_lazybear_wavetrend",
        author="LazyBear",
        name="WaveTrend Oscillator",
        item_type="indicator",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="Double smoothed EMA of price divergence; mathematical basis for VuManChu and Cipher B.",
        pine_reference="TradingView: LazyBear/WaveTrend-Oscillator",
        implementation_fn="calculate_wavetrend",
    ),
    IndicatorMeta(
        id="tv_everget_halftrend",
        author="everget",
        name="HalfTrend",
        item_type="indicator",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="Channel-based trend indicator tracking ATR deviation bounds without repainting.",
        pine_reference="TradingView: everget/HalfTrend",
        implementation_fn="calculate_halftrend",
    ),
    IndicatorMeta(
        id="tv_luxalgo_smc",
        author="LuxAlgo",
        name="Smart Money Concepts (SMC Structure)",
        item_type="indicator",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="Market structure swing highs/lows with strict closed-bar Break of Structure (BOS) & CHoCH.",
        pine_reference="TradingView: LuxAlgo/Smart-Money-Concepts",
        implementation_fn="calculate_smc_structure",
    ),
    IndicatorMeta(
        id="tv_donchian_breakout",
        author="TradingView Originals",
        name="Donchian Channel Breakout",
        item_type="strategy",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="Classic turtle trading high/low n-period envelope for trend following.",
        pine_reference="TradingView: Built-in Donchian Channels",
        implementation_fn="calculate_donchian_channel",
    ),
    IndicatorMeta(
        id="tv_chris_moody_ma",
        author="ChrisMoody",
        name="CM Ultimate MA MTF",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="HIGH_IF_MTF_UNCONFIRMED",
        description="Multi-timeframe moving average overlay with color trend state.",
        pine_reference="TradingView: ChrisMoody/CM_Ultimate_MA_MTF_V2",
    ),
    IndicatorMeta(
        id="tv_hpotter_tdfi",
        author="HPotter",
        name="Trend Direction Force Index",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Cumulative volume and price momentum indicator assessing trend strength.",
        pine_reference="TradingView: HPotter/Trend-Direction-Force-Index",
    ),
    IndicatorMeta(
        id="tv_madrid_squeeze",
        author="Madrid",
        name="Madrid Trend Squeeze",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Multi-period moving average ribbons measuring convergence/divergence.",
        pine_reference="TradingView: Madrid/Madrid-Trend-Squeeze",
    ),
    IndicatorMeta(
        id="tv_glaz_ribbon",
        author="glaz",
        name="Glaz MA Ribbons",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Composite volume and weighted moving average trend filter.",
        pine_reference="TradingView: glaz/glaz-indicators",
    ),
    IndicatorMeta(
        id="tv_ricardo_norm_macd",
        author="RicardoSantos",
        name="Normalized MACD & Hurst Exponent",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Stochastic normalization of MACD oscillators with Hurst persistence.",
        pine_reference="TradingView: RicardoSantos/Normalized-MACD",
    ),
    IndicatorMeta(
        id="tv_alexgrover_tcf",
        author="alexgrover",
        name="Trend Continuation Factor",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="Digital signal processing filters and trend continuation metric.",
        pine_reference="TradingView: alexgrover/Trend-Continuation-Factor",
    ),
    IndicatorMeta(
        id="tv_jdehorty_lorentzian",
        author="jdehorty",
        name="Lorentzian Classification Machine Learning",
        item_type="ml_model",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="k-Nearest Neighbors classifier using Lorentzian distance metric on technical features.",
        pine_reference="TradingView: jdehorty/Lorentzian-Classification",
    ),
    IndicatorMeta(
        id="tv_kaigouthro_ml",
        author="kaigouthro",
        name="Machine Learning Clustering & Direction",
        item_type="ml_model",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="k-Means unsupervised price clustering for support and resistance estimation.",
        pine_reference="TradingView: kaigouthro/ML-Clustering",
    ),
    IndicatorMeta(
        id="tv_kioseff_orderflow",
        author="KioseffTrading",
        name="Institutional Order Flow & Delta",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Tick-volume delta estimation and institutional absorption blocks.",
        pine_reference="TradingView: KioseffTrading/Order-Flow",
    ),
    IndicatorMeta(
        id="tv_lonesometheblue_sr",
        author="LonesomeTheBlue",
        name="Support Resistance Channels",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Dynamic algorithmic support and resistance lines based on pivot confirmation.",
        pine_reference="TradingView: LonesomeTheBlue/Support-Resistance-Channels",
    ),
    IndicatorMeta(
        id="tv_lucf_zigzag",
        author="LucF",
        name="Non-Repainting MTF Framework & ZigZag",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="PineCoders framework for security() calls without historical bar repainting.",
        pine_reference="TradingView: LucF/PineCoders-MTF-Selection",
    ),
    IndicatorMeta(
        id="tv_scarf_ribbon",
        author="scarf",
        name="Multi-MA Ribbon & Momentum",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Cross-sectional moving average cloud with adaptive deviation.",
        pine_reference="TradingView: scarf/Multi-MA-Ribbon",
    ),
    IndicatorMeta(
        id="tv_kodify_trail",
        author="Kodify",
        name="ATR Trailing Stop System",
        item_type="strategy",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="Systematic trailing volatility stops based on high/low ratchets.",
        pine_reference="TradingView: Kodify/ATR-Trailing-Stop",
    ),
    IndicatorMeta(
        id="tv_donovan_rsi_div",
        author="DonovanWall",
        name="RSI Divergence MTF",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="HIGH_IF_MTF_UNCONFIRMED",
        description="Automated pivot-based divergence identification between price and RSI.",
        pine_reference="TradingView: DonovanWall/RSI-Divergence",
    ),
    IndicatorMeta(
        id="tv_e2e4_volatility",
        author="e2e4",
        name="Hilbert Transform Volatility Bands",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Cycle analysis and dominant cycle phase bands via Hilbert transform.",
        pine_reference="TradingView: e2e4/Hilbert-Transform-Bands",
    ),
    IndicatorMeta(
        id="tv_skinra_fvg",
        author="skinra",
        name="Fair Value Gap (FVG) Detector",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="Identifies single-candle liquidity voids between bar t-2 high and bar t low.",
        pine_reference="TradingView: skinra/FVG-Engine",
    ),
    IndicatorMeta(
        id="tv_fikira_structure",
        author="fikira",
        name="Market Structure & Order Flow",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="Order block recognition and liquidity raid markers.",
        pine_reference="TradingView: fikira/Market-Structure",
    ),
    IndicatorMeta(
        id="tv_rumpypumpy_hull",
        author="rumpypumpydumpy",
        name="Hull Moving Average Trend Suite",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Low-lag Hull Moving Average color-trend state machine.",
        pine_reference="TradingView: rumpypumpydumpy/HMA-Suite",
    ),
    IndicatorMeta(
        id="tv_vdubus_binary",
        author="vdubus",
        name="Vdub Binary Directional Strategy",
        item_type="strategy",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Multi-factor envelope and breakout strategy.",
        pine_reference="TradingView: vdubus/Vdub-Binary-Strategy",
    ),
    IndicatorMeta(
        id="tv_immortal_mtf",
        author="ImmortalFreedom",
        name="Multi-Timeframe Trend Confirmation",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="HIGH_IF_MTF_UNCONFIRMED",
        description="Multi-tier timeframe alignment scoring matrix.",
        pine_reference="TradingView: ImmortalFreedom/MTF-Confirmation",
    ),
    # --- Commercial / Proprietary Firms (Audited Equivalents) ---
    IndicatorMeta(
        id="firm_luxalgo_supertrend_ai",
        author="LuxAlgo",
        name="Supertrend AI (Adaptive ATR)",
        item_type="ml_model",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="K-means/clustering guided dynamic ATR factor for Supertrend bands.",
        pine_reference="TradingView: LuxAlgo/Supertrend-AI",
        implementation_fn="calculate_supertrend",
    ),
    IndicatorMeta(
        id="firm_marketcipher_b",
        author="MarketCipher",
        name="Market Cipher B (Proprietary / Audited as WaveTrend + Money Flow)",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Proprietary commercial suite; open equivalent mathematically verified as LazyBear WaveTrend + MFI.",
        pine_reference="Audited equivalent: VuManChu Cipher B / LazyBear WaveTrend",
        implementation_fn="calculate_wavetrend",
    ),
    IndicatorMeta(
        id="firm_tradedots_pivots",
        author="TradeDots",
        name="TradeDots Buy/Sell Signals (Proprietary / Audited as Fractal Pivots)",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="HIGH_IF_MTF_UNCONFIRMED",
        description="Proprietary reversal dots; open equivalent is 5-bar confirmation swing fractal pivots.",
        pine_reference="Audited equivalent: Williams Fractal Pivot Engine",
        implementation_fn="calculate_smc_structure",
    ),
    IndicatorMeta(
        id="firm_chartprime_oscillator",
        author="ChartPrime",
        name="ChartPrime Oscillator Suite",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Proprietary oscillator suite based on normalized Stoch/RSI divergence.",
        pine_reference="Commercial Proprietary - Requires source code audit",
    ),
    IndicatorMeta(
        id="firm_trendspider_raindrops",
        author="TrendSpider",
        name="Raindrop Charts & Anchored VWAP",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="Volume-weighted anchored VWAP starting from key swing session pivots.",
        pine_reference="Commercial API - Pending direct feed integration",
    ),
    IndicatorMeta(
        id="firm_bigshort_smartmoney",
        author="BigShort",
        name="Smart Money Manipulation Index",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="Proprietary dark-pool volume and option dealer gamma proxy.",
        pine_reference="Commercial Data API - Pending broker feed audit",
    ),
    IndicatorMeta(
        id="firm_polycam_breakout",
        author="PolyCam",
        name="Algorithmic Cam Breakouts",
        item_type="strategy",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="Camarilla pivot breakout bands with multi-target levels.",
        pine_reference="TradingView Community: Camarilla Formula",
    ),
    IndicatorMeta(
        id="firm_ticksy_flow",
        author="Ticksy",
        name="Ticksy Micro-Structure Delta",
        item_type="indicator",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="LOW",
        description="High-frequency tick volume imbalance detector.",
        pine_reference="Commercial - Requires Level 2 tick stream",
    ),
    IndicatorMeta(
        id="firm_quantnomad_backtest",
        author="QuantNomad",
        name="QuantNomad Backtest & Execution Suite",
        item_type="strategy",
        status="UNVERIFIED_PENDING_AUDIT",
        repainting_risk="NONE",
        description="Systematic Pine Script backtest framework with commission & slippage.",
        pine_reference="TradingView: QuantNomad Open Library",
    ),
    IndicatorMeta(
        id="firm_hashem_smc_liquidity",
        author="Hashem",
        name="Hashem SMC Liquidity Sweeps",
        item_type="indicator",
        status="VERIFIED_IMPLEMENTED",
        repainting_risk="NONE",
        description="Swing-point liquidity sweep detector based on wick rejections outside swing bounds.",
        pine_reference="TradingView: hashem/SMC-Liquidity",
        implementation_fn="calculate_smc_structure",
    ),
]


def get_catalog() -> list[IndicatorMeta]:
    """Returns the full indicator catalog."""
    return list(INDICATOR_CATALOG)


def get_verified_indicators() -> list[IndicatorMeta]:
    """Returns all indicators verified and implemented with zero repainting."""
    return [item for item in INDICATOR_CATALOG if item.status == "VERIFIED_IMPLEMENTED"]


def get_pending_indicators() -> list[IndicatorMeta]:
    """Returns all indicators pending audit or proprietary closed-source."""
    return [item for item in INDICATOR_CATALOG if item.status == "UNVERIFIED_PENDING_AUDIT"]


def search_catalog(query: str) -> list[IndicatorMeta]:
    """Searches catalog by author, indicator name, or description."""
    q = query.strip().lower()
    if not q:
        return list(INDICATOR_CATALOG)
    return [
        item for item in INDICATOR_CATALOG
        if q in item.author.lower() or q in item.name.lower() or q in item.description.lower() or q in item.id.lower()
    ]
