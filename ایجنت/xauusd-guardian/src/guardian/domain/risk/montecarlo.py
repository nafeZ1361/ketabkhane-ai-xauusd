"""Monte Carlo risk engine — Phase 4 extension (D-026).

Resampling-based risk analysis over a sequence of per-trade **R multiples**
(profit/loss expressed as a multiple of the amount risked on that trade).

What it does:

* resamples the observed sequence either IID (with replacement) or with a
  **moving block bootstrap** that keeps short runs of consecutive trades intact;
* replays each synthetic path with **dynamic sizing** — the risk of trade *i* is
  ``risk_fraction`` of the equity *at that moment*, so a losing run shrinks the
  position and a winning run grows it;
* reports the maximum-drawdown distribution, threshold-exceedance probabilities,
  an explicit ruin definition with its measured frequency, and cost stress;
* is fully deterministic for a given ``(trades, seed, spec)`` and uses ``Decimal``
  arithmetic throughout.

What it is not: a forecast, a guarantee, or a trading system. It re-uses the
observed trades; it cannot invent outcomes that were never sampled, and the
report states that limitation. No ``MetaTrader5``, no account, no orders.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable, Mapping, Sequence

ZERO = Decimal(0)
ONE = Decimal(1)


class MonteCarloError(ValueError):
    """Raised when a simulation request is inconsistent or cannot be run safely."""


def _dec(name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise MonteCarloError(f"{name} must be Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise MonteCarloError(f"{name} must be finite")
    return value


def _int(name: str, value: object, *, minimum: int, maximum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MonteCarloError(f"{name} must be int")
    if value < minimum:
        raise MonteCarloError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise MonteCarloError(f"{name} must be <= {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class MonteCarloSpec:
    """All inputs that influence a simulation, so a run is reproducible."""

    simulations: int
    seed: int
    mode: str  # "iid" | "block"
    block_size: int
    initial_equity: Decimal
    risk_fraction: Decimal
    ruin_fraction: Decimal
    cost_r: Decimal = ZERO
    cost_multiplier: Decimal = ONE
    dd_thresholds: tuple[Decimal, ...] = (Decimal("0.10"), Decimal("0.20"), Decimal("0.30"))

    def __post_init__(self) -> None:
        _int("simulations", self.simulations, minimum=1, maximum=1_000_000)
        _int("seed", self.seed, minimum=0)
        _int("block_size", self.block_size, minimum=1, maximum=100_000)
        if self.mode not in ("iid", "block"):
            raise MonteCarloError("mode must be 'iid' or 'block'")
        _dec("initial_equity", self.initial_equity)
        _dec("risk_fraction", self.risk_fraction)
        _dec("ruin_fraction", self.ruin_fraction)
        _dec("cost_r", self.cost_r)
        _dec("cost_multiplier", self.cost_multiplier)
        if self.initial_equity <= 0:
            raise MonteCarloError("initial_equity must be positive")
        if not (ZERO < self.risk_fraction < ONE):
            raise MonteCarloError("risk_fraction must be strictly between 0 and 1")
        if not (ZERO < self.ruin_fraction <= ONE):
            raise MonteCarloError("ruin_fraction must be in (0, 1]")
        if self.cost_r < 0:
            raise MonteCarloError("cost_r must be >= 0")
        if self.cost_multiplier <= 0:
            raise MonteCarloError("cost_multiplier must be positive")
        for threshold in self.dd_thresholds:
            _dec("dd_threshold", threshold)
            if not (ZERO <= threshold < ONE):
                raise MonteCarloError("dd_thresholds must be in [0, 1)")


@dataclass(frozen=True, slots=True)
class SimulationSummary:
    simulations: int
    ruined: int
    ruin_frequency: Decimal
    mean_max_drawdown: Decimal
    p50_max_drawdown: Decimal
    p90_max_drawdown: Decimal
    p95_max_drawdown: Decimal
    p99_max_drawdown: Decimal
    exceedance: Mapping[str, Decimal] = field(default_factory=dict)
    mean_final_equity: Decimal = ZERO
    median_final_equity: Decimal = ZERO
    min_final_equity: Decimal = ZERO
    trading_days: int = 0

    def as_dict(self) -> dict[str, object]:
        def s(value: Decimal) -> str:
            return format(value, "f")

        return {
            "simulations": self.simulations,
            "ruined": self.ruined,
            "ruin_frequency": s(self.ruin_frequency),
            "mean_max_drawdown": s(self.mean_max_drawdown),
            "p50_max_drawdown": s(self.p50_max_drawdown),
            "p90_max_drawdown": s(self.p90_max_drawdown),
            "p95_max_drawdown": s(self.p95_max_drawdown),
            "p99_max_drawdown": s(self.p99_max_drawdown),
            "exceedance": {k: s(v) for k, v in self.exceedance.items()},
            "mean_final_equity": s(self.mean_final_equity),
            "median_final_equity": s(self.median_final_equity),
            "min_final_equity": s(self.min_final_equity),
        }


def _percentile(ordered: Sequence[Decimal], q: Decimal) -> Decimal:
    if not ordered:
        raise MonteCarloError("empty sample")
    # nearest-rank on a sorted list; deterministic and free of interpolation bias
    index = int((q * Decimal(len(ordered))).to_integral_value(rounding="ROUND_CEILING")) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _sample_iid(rng: random.Random, size: int, n: int) -> list[int]:
    return [rng.randrange(n) for _ in range(size)]


def _sample_block(rng: random.Random, size: int, n: int, block: int) -> list[int]:
    """Moving block bootstrap: contiguous (wrapping) runs of the observed order."""
    out: list[int] = []
    while len(out) < size:
        start = rng.randrange(n)
        for offset in range(block):
            out.append((start + offset) % n)
            if len(out) == size:
                break
    return out


def simulate(r_multiples: Sequence[Decimal], spec: MonteCarloSpec) -> SimulationSummary:
    """Replay ``spec.simulations`` synthetic paths over the observed R multiples."""
    if not isinstance(spec, MonteCarloSpec):
        raise MonteCarloError("spec must be a MonteCarloSpec")
    if isinstance(r_multiples, (str, bytes)) or not isinstance(r_multiples, Sequence):
        raise MonteCarloError("r_multiples must be a sequence of Decimal")
    if len(r_multiples) < 1:
        raise MonteCarloError("r_multiples must contain at least one trade")
    for value in r_multiples:
        _dec("r_multiple", value)

    trades = list(r_multiples)
    n = len(trades)
    size = n  # one synthetic history = the same number of trades as observed
    rng = random.Random(spec.seed)
    cost = spec.cost_r * spec.cost_multiplier
    ruin_level = spec.initial_equity * (ONE - spec.ruin_fraction)

    drawdowns: list[Decimal] = []
    final_equities: list[Decimal] = []
    ruined = 0
    exceed_counts = {format(t, "f"): 0 for t in spec.dd_thresholds}

    for _ in range(spec.simulations):
        indices = (
            _sample_iid(rng, size, n)
            if spec.mode == "iid"
            else _sample_block(rng, size, n, spec.block_size)
        )
        equity = spec.initial_equity
        peak = equity
        worst = ZERO
        is_ruined = False

        for index in indices:
            risk = equity * spec.risk_fraction
            equity += risk * (trades[index] - cost)
            if equity > peak:
                peak = equity
            if peak > 0:
                drawdown = (peak - equity) / peak
                if drawdown > worst:
                    worst = drawdown
            if equity <= 0 or equity <= ruin_level:
                is_ruined = True
                break

        drawdowns.append(worst if worst <= ONE else ONE)
        final_equities.append(equity if equity > 0 else ZERO)
        if is_ruined:
            ruined += 1
        for threshold in spec.dd_thresholds:
            if worst >= threshold:
                exceed_counts[format(threshold, "f")] += 1

    drawdowns.sort()
    final_equities.sort()
    count = Decimal(spec.simulations)

    return SimulationSummary(
        simulations=spec.simulations,
        ruined=ruined,
        ruin_frequency=(Decimal(ruined) / count).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN),
        mean_max_drawdown=(sum(drawdowns) / count).quantize(Decimal("0.000001")),
        p50_max_drawdown=_percentile(drawdowns, Decimal("0.50")),
        p90_max_drawdown=_percentile(drawdowns, Decimal("0.90")),
        p95_max_drawdown=_percentile(drawdowns, Decimal("0.95")),
        p99_max_drawdown=_percentile(drawdowns, Decimal("0.99")),
        exceedance={
            key: (Decimal(value) / count).quantize(Decimal("0.000001"))
            for key, value in exceed_counts.items()
        },
        mean_final_equity=(sum(final_equities) / count).quantize(Decimal("0.01")),
        median_final_equity=_percentile(final_equities, Decimal("0.50")),
        min_final_equity=final_equities[0],
    )


def compare_strategies(
    strategies: Mapping[str, Sequence[Decimal]], spec: MonteCarloSpec
) -> dict[str, SimulationSummary]:
    """Run the same spec (same seed) over several strategies for a fair comparison."""
    if not isinstance(strategies, Mapping) or not strategies:
        raise MonteCarloError("strategies must be a non-empty mapping")
    return {name: simulate(trades, spec) for name, trades in strategies.items()}


def sensitivity(
    r_multiples: Sequence[Decimal],
    spec: MonteCarloSpec,
    *,
    win_rate_deltas: Iterable[Decimal] = (Decimal("-0.10"), ZERO, Decimal("0.10")),
    rr_multipliers: Iterable[Decimal] = (Decimal("0.75"), ONE, Decimal("1.25")),
    horizon: int | None = None,
) -> list[dict[str, object]]:
    """Parametric grid: resample a Bernoulli trade stream with shifted win rate / RR.

    The observed sample supplies ``p`` (win rate), ``avg_win`` and ``avg_loss`` (in R).
    Each cell regenerates ``horizon`` trades from a seeded RNG with ``p + delta`` and
    ``avg_win × rr``, then replays the same dynamic-sizing engine. This is a *model*:
    it assumes independence and stable payoff magnitudes — the report says so.
    """
    trades = list(r_multiples)
    if not trades:
        raise MonteCarloError("r_multiples must not be empty")
    wins = [r for r in trades if r > 0]
    losses = [r for r in trades if r < 0]
    if not wins or not losses:
        raise MonteCarloError("sensitivity needs both winning and losing trades")
    base_p = Decimal(len(wins)) / Decimal(len(trades))
    avg_win = sum(wins) / Decimal(len(wins))
    avg_loss = sum(losses) / Decimal(len(losses))
    steps = horizon or len(trades)

    out: list[dict[str, object]] = []
    cell = 0
    for delta in win_rate_deltas:
        probability = base_p + Decimal(delta)
        if not (ZERO < probability < ONE):
            raise MonteCarloError(f"win rate out of range for delta {delta}")
        for rr in rr_multipliers:
            if rr <= 0:
                raise MonteCarloError("rr multipliers must be positive")
            rng = random.Random(spec.seed + cell)
            payoff_win = avg_win * Decimal(rr)
            synthetic = [
                payoff_win if rng.random() < float(probability) else avg_loss
                for _ in range(steps)
            ]
            summary = simulate(synthetic, spec)
            out.append(
                {
                    "win_rate": format(probability.quantize(Decimal("0.0001")), "f"),
                    "rr_multiplier": format(Decimal(rr), "f"),
                    "ruin_frequency": format(summary.ruin_frequency, "f"),
                    "p95_max_drawdown": format(summary.p95_max_drawdown, "f"),
                    "mean_final_equity": format(summary.mean_final_equity, "f"),
                }
            )
            cell += 1
    return out


def canonical_digest(payload: Mapping[str, object]) -> str:
    """SHA-256 of a canonical JSON rendering (sorted keys, no whitespace)."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
