"""Deterministic verdict from pre-registered gates."""

from __future__ import annotations

PASS, FAIL, INSUFFICIENT = "PASS", "FAIL", "INSUFFICIENT_EVIDENCE"


def evaluate(metrics: dict, min_trades: int = 30, pf_min: float = 1.0, dd_max: float = 1000.0) -> str:
    trades = int(metrics.get("trades", 0))
    if trades < min_trades:
        return INSUFFICIENT
    pf = metrics.get("profit_factor", 0.0)
    dd = metrics.get("max_drawdown", 0.0)
    if pf is None or pf <= pf_min or dd > dd_max:
        return FAIL
    return PASS
