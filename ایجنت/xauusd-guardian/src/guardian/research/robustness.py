"""Seeded trade-sequence bootstrap and drawdown distribution."""
from __future__ import annotations
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    total_pnls: tuple[Decimal, ...]
    max_drawdowns: tuple[Decimal, ...]
    max_drawdown_fractions: tuple[Decimal, ...]
    ruin_count: int
    block_size: int

    @property
    def simulations(self) -> int:
        return len(self.total_pnls)

    def quantile(self, values: tuple[Decimal, ...], q: Decimal) -> Decimal:
        if not values or not isinstance(q, Decimal) or not q.is_finite() or not Decimal(0) <= q <= Decimal(1):
            raise ValueError("non-empty values and finite q in [0,1] required")
        ordered = sorted(values)
        return ordered[int(Decimal(len(ordered) - 1) * q)]

    def percentile_summary(self) -> dict[str, dict[str, Decimal]]:
        qs = (("p05", Decimal(".05")), ("p25", Decimal(".25")), ("p50", Decimal(".50")),
              ("p75", Decimal(".75")), ("p95", Decimal(".95")))
        return {
            "total_pnl": {name: self.quantile(self.total_pnls, q) for name, q in qs},
            "max_drawdown": {name: self.quantile(self.max_drawdowns, q) for name, q in qs},
            "max_drawdown_fraction": {name: self.quantile(self.max_drawdown_fractions, q) for name, q in qs},
        }

def monte_carlo_trades(trade_pnls: Sequence[Decimal], *, simulations: int = 2000, seed: int = 7,
                       starting_equity: Decimal = Decimal("10000"), block_size: int = 1) -> MonteCarloResult:
    """Bootstrap n-trade paths. block_size=1 is IID; >1 is moving-block bootstrap."""
    if not trade_pnls:
        raise ValueError("at least one trade PnL is required")
    if isinstance(simulations, bool) or not isinstance(simulations, int) or simulations < 1:
        raise ValueError("simulations must be a positive integer")
    if isinstance(block_size, bool) or not isinstance(block_size, int) or not 1 <= block_size <= len(trade_pnls):
        raise ValueError("block_size must be an integer in [1, trade_count]")
    if not isinstance(starting_equity, Decimal) or not starting_equity.is_finite() or starting_equity <= 0:
        raise ValueError("starting_equity must be a positive finite Decimal")
    if any(not isinstance(x, Decimal) or not x.is_finite() for x in trade_pnls):
        raise ValueError("all trade PnLs must be finite Decimals")
    rng = random.Random(seed)
    totals, drawdowns, drawdown_fractions = [], [], []
    ruin, n = 0, len(trade_pnls)
    valid_starts = n - block_size + 1
    for _ in range(simulations):
        sample = []
        while len(sample) < n:
            start = rng.randrange(valid_starts)
            sample.extend(trade_pnls[start:start + block_size])
        equity = peak = starting_equity
        max_dd = total = Decimal(0)
        ruined = False
        for pnl in sample[:n]:
            total += pnl
            equity += pnl
            ruined = ruined or equity <= 0
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        totals.append(total)
        drawdowns.append(max_dd)
        drawdown_fractions.append(max_dd / peak if peak > 0 else Decimal(1))
        ruin += int(ruined)
    return MonteCarloResult(tuple(totals), tuple(drawdowns), tuple(drawdown_fractions), ruin, block_size)

def compare_bootstrap_methods(trade_pnls: Sequence[Decimal], *, simulations: int = 2000, seed: int = 7,
                              starting_equity: Decimal = Decimal("10000"), block_size: int = 3
                              ) -> tuple[MonteCarloResult, MonteCarloResult]:
    """Return IID and moving-block results using the same reproducible seed."""
    iid = monte_carlo_trades(trade_pnls, simulations=simulations, seed=seed,
                             starting_equity=starting_equity, block_size=1)
    blocked = monte_carlo_trades(trade_pnls, simulations=simulations, seed=seed,
                                 starting_equity=starting_equity, block_size=block_size)
    return iid, blocked
