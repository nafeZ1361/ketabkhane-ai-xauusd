"""Deterministic walk-forward split generator.

No data loading, no thresholds, no metrics: only index arithmetic so the output
can be tested independently from the engine.

Layout of one split::

    [ train_start .. train_stop )  gap(purge+embargo)  [ test_start .. test_stop )

- train is truncated by `purge` samples so the model never sees the boundary
- `embargo` adds a gap between the training block and the test block
- consecutive splits advance by `step` (default: test_size)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Split:
    index: int
    train_start: int
    train_stop: int
    test_start: int
    test_stop: int

    def train(self) -> range:
        return range(self.train_start, self.train_stop)

    def test(self) -> range:
        return range(self.test_start, self.test_stop)

    @property
    def gap(self) -> int:
        return self.test_start - self.train_stop


def walk_forward(n: int, train_size: int, test_size: int, step: int | None = None,
                 purge: int = 0, embargo: int = 0) -> list[Split]:
    if n <= 0:
        raise ValueError("n must be positive")
    for name, value in (("train_size", train_size), ("test_size", test_size)):
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if purge < 0 or embargo < 0:
        raise ValueError("purge and embargo must not be negative")
    if purge >= train_size:
        raise ValueError("purge must be smaller than train_size")
    step = test_size if step is None else step
    if step <= 0:
        raise ValueError("step must be positive")

    splits: list[Split] = []
    start = 0
    index = 0
    while True:
        train_stop = start + train_size - purge
        test_start = start + train_size + embargo
        test_stop = test_start + test_size
        if test_stop > n:
            break
        splits.append(Split(index, start, train_stop, test_start, test_stop))
        start += step
        index += 1
    return splits
