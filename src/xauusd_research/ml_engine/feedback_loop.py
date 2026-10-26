"""Continuous Machine Learning Feedback Loop & Adaptive Parameter Optimizer.

Evaluates trade executions post-mortem, diagnoses failure modes (e.g. choppy whipsaws,
spread drag, volatility blowouts), logs to structured JSONL, and dynamically adjusts
risk weights and ATR multipliers to improve subsequent model iterations.
"""
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence
from .regime_tree import MarketRegime, RegimeClassification


@dataclass(frozen=True)
class TradeRecord:
    trade_id: str
    entry_time: str
    exit_time: str
    direction: int  # 1 = Long, -1 = Short
    entry_price: float
    exit_price: float
    pnl: float
    gross_pnl: float
    costs: float
    entry_regime: MarketRegime
    exit_regime: MarketRegime
    bars_held: int


@dataclass(frozen=True)
class TradeOutcomeDiagnosis:
    trade_id: str
    pnl: float
    error_category: str  # "NONE" | "CHOP_WHIPSAW" | "VOL_SHOCK_LOSS" | "PREMATURE_EXIT" | "SPREAD_OVERRUN"
    root_cause: str
    adaptive_recommendation: str


@dataclass
class AdaptiveParameters:
    atr_stop_multiplier: float = 3.0
    min_trend_confidence: float = 0.65
    lockout_in_shock: bool = True
    chop_size_reduction: float = 0.5


class FeedbackLedger:
    """Manages append-only JSONL diagnostic ledger for continuous learning."""

    def __init__(self, ledger_path: Path | None = None) -> None:
        self.ledger_path = ledger_path
        self.diagnoses: list[TradeOutcomeDiagnosis] = []

    def record(self, diagnosis: TradeOutcomeDiagnosis) -> None:
        self.diagnoses.append(diagnosis)
        if self.ledger_path:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(diagnosis)) + "\n")

    def summary_stats(self) -> dict[str, Any]:
        total = len(self.diagnoses)
        if total == 0:
            return {"total_trades": 0, "error_breakdown": {}}
        breakdown: dict[str, int] = {}
        for d in self.diagnoses:
            breakdown[d.error_category] = breakdown.get(d.error_category, 0) + 1
        return {
            "total_trades": total,
            "error_breakdown": breakdown,
        }


class AdaptiveFeedbackLoop:
    """Feedback Loop Engine that diagnoses trades and retrains parameter boundaries."""

    def __init__(self, ledger: FeedbackLedger | None = None) -> None:
        self.ledger = ledger or FeedbackLedger()
        self.params = AdaptiveParameters()

    def diagnose_trade(self, trade: TradeRecord) -> TradeOutcomeDiagnosis:
        if trade.pnl > 0:
            diag = TradeOutcomeDiagnosis(
                trade_id=trade.trade_id,
                pnl=trade.pnl,
                error_category="NONE",
                root_cause="Clean execution in alignment with regime.",
                adaptive_recommendation="MAINTAIN_CURRENT_WEIGHTS",
            )
            self.ledger.record(diag)
            return diag

        # Diagnosing Loss Modes
        # 1. Spread overrun: Gross PnL was positive or near zero, but fees turned it into loss
        if trade.gross_pnl >= -0.10 and trade.costs > abs(trade.pnl * 0.5):
            diag = TradeOutcomeDiagnosis(
                trade_id=trade.trade_id,
                pnl=trade.pnl,
                error_category="SPREAD_OVERRUN",
                root_cause="Transaction costs and spread exceeded trade movement.",
                adaptive_recommendation="INCREASE_MIN_PROFIT_TARGET",
            )
        # 2. Volatility Shock hit
        elif trade.entry_regime == MarketRegime.VOLATILITY_SHOCK or trade.exit_regime == MarketRegime.VOLATILITY_SHOCK:
            diag = TradeOutcomeDiagnosis(
                trade_id=trade.trade_id,
                pnl=trade.pnl,
                error_category="VOL_SHOCK_LOSS",
                root_cause="Position held during severe volatility expansion.",
                adaptive_recommendation="ENFORCE_HARD_CASH_LOCKOUT",
            )
        # 3. Chop Whipsaw
        elif trade.entry_regime == MarketRegime.CHOPPY_RANGE:
            diag = TradeOutcomeDiagnosis(
                trade_id=trade.trade_id,
                pnl=trade.pnl,
                error_category="CHOP_WHIPSAW",
                root_cause="Trend trade initiated in oscillating non-directional regime.",
                adaptive_recommendation="FILTER_CHOP_ENTRIES_OR_REDUCE_SIZE",
            )
        # 4. Premature exit / noise stop
        elif trade.bars_held <= 2:
            diag = TradeOutcomeDiagnosis(
                trade_id=trade.trade_id,
                pnl=trade.pnl,
                error_category="PREMATURE_EXIT",
                root_cause="Stop loss was placed within normal ATR noise band.",
                adaptive_recommendation="WIDEN_ATR_STOP_MULTIPLIER",
            )
        else:
            diag = TradeOutcomeDiagnosis(
                trade_id=trade.trade_id,
                pnl=trade.pnl,
                error_category="GENERIC_LOSS",
                root_cause="Normal adverse price movement.",
                adaptive_recommendation="NORMAL_CYCLE",
            )

        self.ledger.record(diag)
        return diag

    def adapt_parameters(self) -> AdaptiveParameters:
        """Dynamically tunes parameters based on diagnosed failure frequencies."""
        stats = self.ledger.summary_stats()
        breakdown = stats.get("error_breakdown", {})
        total = stats.get("total_trades", 0)
        if total == 0:
            return self.params

        chop_errors = breakdown.get("CHOP_WHIPSAW", 0)
        premature_errors = breakdown.get("PREMATURE_EXIT", 0)
        vol_errors = breakdown.get("VOL_SHOCK_LOSS", 0)

        # If more than 25% of losses are due to chop whipsaws, raise trend confidence requirement
        if chop_errors / total >= 0.25:
            self.params.min_trend_confidence = min(0.85, self.params.min_trend_confidence + 0.05)
            self.params.chop_size_reduction = max(0.2, self.params.chop_size_reduction - 0.1)

        # If premature stopouts occur frequently, widen ATR stop
        if premature_errors / total >= 0.20:
            self.params.atr_stop_multiplier = min(4.5, self.params.atr_stop_multiplier + 0.25)

        # If volatility shock losses occur, enforce lockout
        if vol_errors > 0:
            self.params.lockout_in_shock = True

        return self.params
