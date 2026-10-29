"""Minimal strategy generator (A4): deterministic search-space sampling.

Only MA-crossover specs are executable by the current backtester; other types
are declared for future engines and marked not executable here.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .strategies import StrategySpec

SPACE = {
    "ma": ((5, 20), (10, 50), (20, 100), (50, 200), (100, 400)),
    "breakout": ((20, 10), (50, 20), (100, 40), (200, 60)),
    "mean_reversion": ((20, 2.0), (50, 2.5), (100, 3.0)),
}


@dataclass(frozen=True)
class GeneratedStrategy:
    spec: StrategySpec
    family: str
    executable: bool


def generate(count: int = 5, seed: int = 0) -> list[GeneratedStrategy]:
    rng = random.Random(seed)
    out: list[GeneratedStrategy] = []
    for i in range(count):
        family = "ma" if i % 2 == 0 else rng.choice(["breakout", "mean_reversion"])
        params = rng.choice(SPACE[family])
        if family == "ma":
            spec = StrategySpec(f"gen_ma_{params[0]}_{params[1]}", params[0], params[1])
        else:
            spec = StrategySpec(f"gen_{family}_{params[0]}", params[0], 0)
        out.append(GeneratedStrategy(spec=spec, family=family, executable=family == "ma"))
    return out
