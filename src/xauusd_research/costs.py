"""Broker cost model.

A cost profile is data, not a guess: every field must be supplied from a
documented source. Missing values are rejected instead of defaulted, because an
unknown cost presented as real would invalidate every research result.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_NUMERIC = (
    "contract_size", "point_size", "tick_size", "tick_value",
    "spread_points", "slippage_points", "commission_per_lot_round_turn",
    "lots", "min_lot", "lot_step",
)

LABEL_NO_COSTS = "NO_TRADING_COSTS"
LABEL_PROVISIONAL = "PROVISIONAL_COST_SCENARIO"
LABEL_VERIFIED = "VERIFIED_COSTS"


class UnknownSpecError(ValueError):
    """Raised when a broker specification is absent or incomplete."""


@dataclass(frozen=True)
class BrokerProfile:
    profile_id: str
    symbol: str
    contract_size: float
    point_size: float
    tick_size: float
    tick_value: float
    spread_points: float
    slippage_points: float
    commission_per_lot_round_turn: float
    lots: float
    min_lot: float
    lot_step: float
    verified: bool
    source: str

    @classmethod
    def from_dict(cls, data: dict) -> "BrokerProfile":
        missing = [key for key in REQUIRED_NUMERIC if data.get(key) is None]
        for key in ("profile_id", "symbol", "source"):
            if not str(data.get(key) or "").strip():
                missing.append(key)
        if missing:
            raise UnknownSpecError(
                "broker specification is incomplete, refusing to guess: " + ", ".join(sorted(set(missing)))
            )
        values = {key: float(data[key]) for key in REQUIRED_NUMERIC}
        if values["contract_size"] <= 0 or values["point_size"] <= 0 or values["lots"] <= 0:
            raise UnknownSpecError("contract_size, point_size and lots must be positive")
        if values["lots"] < values["min_lot"]:
            raise UnknownSpecError("lots is below min_lot")
        if values["lot_step"] > 0 and abs(round(values["lots"] / values["lot_step"]) * values["lot_step"] - values["lots"]) > 1e-9:
            raise UnknownSpecError("lots is not a multiple of lot_step")
        for key in ("spread_points", "slippage_points", "commission_per_lot_round_turn", "tick_size", "tick_value"):
            if values[key] < 0:
                raise UnknownSpecError(f"{key} must not be negative")
        return cls(profile_id=str(data["profile_id"]), symbol=str(data["symbol"]), verified=bool(data.get("verified", False)),
                   source=str(data["source"]), **values)

    @classmethod
    def load(cls, path) -> "BrokerProfile":
        path = Path(path)
        if not path.is_file():
            raise UnknownSpecError(f"broker profile not found: {path}")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @property
    def label(self) -> str:
        return LABEL_VERIFIED if self.verified else LABEL_PROVISIONAL

    def cost_per_trade(self) -> float:
        """Round-turn cost in account currency for the configured lot size."""
        price_cost = (self.spread_points + self.slippage_points) * self.point_size
        return price_cost * self.contract_size * self.lots + self.commission_per_lot_round_turn * self.lots

    def net_pnl(self, entry_price: float, exit_price: float) -> float:
        gross = (exit_price - entry_price) * self.contract_size * self.lots
        return round(gross - self.cost_per_trade(), 6)

    def describe(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "symbol": self.symbol,
            "source": self.source,
            "verified": self.verified,
            "contract_size": self.contract_size,
            "point_size": self.point_size,
            "spread_points": self.spread_points,
            "slippage_points": self.slippage_points,
            "commission_per_lot_round_turn": self.commission_per_lot_round_turn,
            "lots": self.lots,
            "cost_per_trade": round(self.cost_per_trade(), 6),
        }