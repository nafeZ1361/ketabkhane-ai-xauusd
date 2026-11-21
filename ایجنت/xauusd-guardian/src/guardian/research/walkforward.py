"""Chronological expanding walk-forward folds with purge and embargo."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    number: int
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def walk_forward_folds(
    sample_count: int,
    *,
    initial_train_size: int,
    test_size: int,
    step_size: int | None = None,
    purge_bars: int = 0,
    embargo_bars: int = 0,
) -> tuple[WalkForwardFold, ...]:
    values = (sample_count, initial_train_size, test_size, purge_bars, embargo_bars)
    if any(isinstance(x, bool) or not isinstance(x, int) for x in values):
        raise ValueError("fold sizes must be integers")
    step = test_size if step_size is None else step_size
    if isinstance(step, bool) or not isinstance(step, int):
        raise ValueError("step_size must be an integer")
    if sample_count < 1 or initial_train_size < 2 or test_size < 1 or step < 1 or purge_bars < 0 or embargo_bars < 0:
        raise ValueError("invalid walk-forward sizes")
    folds: list[WalkForwardFold] = []
    test_start = initial_train_size
    previous_test_end = 0
    number = 1
    while test_start + test_size <= sample_count:
        train_end = test_start - purge_bars
        train = list(range(train_end))
        if previous_test_end:
            embargo_start = previous_test_end
            embargo_end = min(sample_count, previous_test_end + embargo_bars)
            train = [i for i in train if not embargo_start <= i < embargo_end]
        test = tuple(range(test_start, test_start + test_size))
        if len(train) >= 2:
            folds.append(WalkForwardFold(number, tuple(train), test))
        previous_test_end = test_start + test_size
        test_start += step
        number += 1
    return tuple(folds)
