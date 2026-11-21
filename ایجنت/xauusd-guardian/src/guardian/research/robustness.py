"""Seeded trade-sequence Monte Carlo and drawdown distribution."""
from __future__ import annotations
import random
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    total_pnls: tuple[Decimal, ...]
    max_drawdowns: tuple[Decimal, ...]
    ruin_count: int

    @property
    def simulations(self) -> int:
        return len(self.total_pnls)

    def quantile(self, values: tuple[Decimal, ...], q: Decimal) -> Decimal:
        if not values or not Decimal(0) <= q <= Decimal(1):
            raise ValueError("non-empty values and q in [0,1] required")
        ordered = sorted(values)
        index = int((Decimal(len(ordered) - 1) * q).to_integral_value(rounding="ROUND_FLOOR"))
        return ordered[index]


def monte_carlo_trades(
    trade_pnls: tuple[Decimal, ...] | list[Decimal],
    *,
    simulations: int = 1000,
    seed: int = 7,
    starting_equity: Decimal = Decimal("10000"),
) -> MonteCarloResult:
    if not trade_pnls:
        raise ValueError("at least one trade PnL is required")
    if isinstance(simulations, bool) or not isinstance(simulations, int) or simulations < 1:
        raise ValueError("simulations must be a positive integer")
    if not isinstance(starting_equity, Decimal) or not starting_equity.is_finite() or starting_equity <= 0:
        raise ValueError("starting_equity must be a positive finite Decimal")
    if any(not isinstance(x, Decimal) or not x.is_finite() for x in trade_pnls):
        raise ValueError("all trade PnLs must be finite Decimals")
    rng = random.Random(seed)
    totals: list[Decimal] = []
    drawdowns: list[Decimal] = []
    ruin = 0
    n = len(trade_pnls)
    for _ in range(simulations):
        equity = starting_equity
        peak = equity
        max_dd = Decimal(0)
        total = Decimal(0)
        for _ in range(n):
            pnl = trade_pnls[rng.randrange(n)]
            total += pnl
            equity += pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        totals.append(total)
        drawdowns.append(max_dd)
        ruin += equity <= 0
    return MonteCarloResult(tuple(totals), tuple(drawdowns), ruin)
