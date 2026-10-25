"""Statistical validation metrics (Charter v2.0, section 14).

Implements, from first principles (no third-party dependencies):
- ``probabilistic_sharpe_ratio``  : PSR (Bailey & Lopez de Prado 2014)
- ``deflated_sharpe_ratio``       : DSR with SR* derived from the trial set
- ``cscv_pbo``                    : Probability of Backtest Overfitting via CSCV
- ``block_bootstrap_ci``          : moving-block bootstrap CI for a statistic

Conventions:
- ``returns`` are per-trade or per-bar returns; Sharpe is computed with the
  standard skew/kurtosis correction where requested, otherwise plain i.i.d.
- All functions return floats/structures that JSON-serialize cleanly so they
  can be embedded in ledger records verbatim.
- Determinism: every stochastic routine takes an explicit ``seed`` and uses
  only ``random.Random(seed)`` (acceptance test AT-STAT-04 reproduction).
"""

from __future__ import annotations

import math
import random
from statistics import NormalDist

_NORMAL = NormalDist()


# --------------------------------------------------------------------- basics
def _mean(xs):
    return sum(xs) / len(xs)


def _std(xs):
    if len(xs) < 2:
        raise ValueError("need at least two observations")
    mu = _mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def _skew(xs):
    """Adjusted Fisher-Pearson standardized moment coefficient G1."""
    n = len(xs)
    if n < 3:
        return 0.0
    mu = _mean(xs)
    s = _std(xs)
    if s == 0:
        return 0.0
    m3 = sum((x - mu) ** 3 for x in xs) / n
    g1 = m3 / s ** 3
    return math.sqrt(n * (n - 1)) / (n - 2) * g1


def _kurt(xs):
    """Excess kurtosis, sample-corrected (G2), non-normal when negative."""
    n = len(xs)
    if n < 4:
        return 0.0
    mu = _mean(xs)
    s = _std(xs)
    if s == 0:
        return 0.0
    m4 = sum((x - mu) ** 4 for x in xs) / n
    g2 = m4 / s ** 4 - 3.0
    return ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * g2 + 6.0)


def sharpe_ratio(returns, periods_per_year=None):
    """Annualized-or-raw Sharpe of a return series (sample std)."""
    sr = _mean(returns) / _std(returns)
    if periods_per_year:
        return sr * math.sqrt(periods_per_year)
    return sr


# ------------------------------------------------------------------------ PSR
def probabilistic_sharpe_ratio(returns, sr_benchmark=0.0):
    """PSR: probability that the true Sharpe exceeds ``sr_benchmark``.

    Bailey & Lopez de Prado (2014), Eq. 5 — includes skew and excess-kurtosis
    correction. Returns a float in (0, 1). Raises on degenerate input.
    """
    n = len(returns)
    if n < 8:
        raise ValueError("PSR requires at least 8 observations")
    std = _std(returns)
    if std == 0:
        raise ValueError("PSR is undefined for a constant return series")
    sr = _mean(returns) / std
    skew = _skew(returns)
    kurt = _kurt(returns)
    denom = math.sqrt(max(1.0 - skew * sr + (kurt / 4.0) * sr ** 2, 1e-12) / (n - 1))
    z = (sr - sr_benchmark) / denom
    return _NORMAL.cdf(z)


# ------------------------------------------------------------------------ DSR
def expected_max_sr(num_trials, sr_std=1.0):
    """E[max SR] across ``num_trials`` independent draws under the null.

    Euler-Mascheroni approximation of the extreme-value expectation:
    ``(1 - gamma) * Z^-1(1 - 1/N) + gamma * Z^-1(1 - 1/(N*e))``
    scaled by ``sr_std``.
    """
    if num_trials < 2:
        return 0.0
    gamma = 0.5772156649015329
    e = math.e
    z1 = _NORMAL.inv_cdf(1.0 - 1.0 / num_trials)
    z2 = _NORMAL.inv_cdf(1.0 - 1.0 / (num_trials * e))
    return ((1.0 - gamma) * z1 + gamma * z2) * sr_std


def deflated_sharpe_ratio(trial_sharpes, candidate_index=0):
    """DSR over a set of observed (per-observation-unit) Sharpe ratios.

    ``trial_sharpes`` must contain one Sharpe per trial run (the experiment
    ledger provides these). The benchmark SR* is derived from the spread of
    the trial Sharpes themselves, so no external constant is invented.
    Returns ``None`` when N < 2 (gate stays INACTIVE — never report a number
    the sample cannot support).
    """
    n_trials = len(trial_sharpes)
    if n_trials < 2:
        return None
    sigma = _std([float(s) for s in trial_sharpes])
    sr_star = expected_max_sr(n_trials, sr_std=sigma)
    candidate = float(trial_sharpes[candidate_index])
    # PSR of the best trial against the multiple-testing benchmark.
    # We approximate the per-trial return length as unknown here; callers pass
    # full returns to probabilistic_sharpe_ratio when available. This variant
    # uses the normal CDF on the standardized gap directly.
    gap = candidate - sr_star
    return _NORMAL.cdf(gap / max(sigma, 1e-12))


# ------------------------------------------------------------------ block CI
def block_bootstrap_ci(observations, statistic, block_size=60, alpha=0.05,
                       samples=2000, seed=20261026):
    """Moving-block bootstrap confidence interval for ``statistic``.

    Preserves serial dependence by resampling contiguous blocks (Charter gate:
    ``bootstrap.block_size``). Returns dict with point estimate, lower/upper
    bounds and the deterministic seed used.
    """
    n = len(observations)
    if n < block_size:
        raise ValueError("series shorter than bootstrap block size")
    rng = random.Random(seed)
    point = statistic(observations)
    num_blocks = max(1, math.ceil(n / block_size))
    stats = []
    for _ in range(samples):
        resampled = []
        for _b in range(num_blocks):
            start = rng.randrange(0, n - block_size + 1)
            resampled.extend(observations[start:start + block_size])
        stats.append(statistic(resampled[:n]))
    stats.sort()
    lo_idx = int(math.floor((alpha / 2.0) * samples))
    hi_idx = int(math.floor((1.0 - alpha / 2.0) * samples)) - 1
    return {
        "point": point,
        "lower": stats[lo_idx],
        "upper": stats[min(hi_idx, samples - 1)],
        "block_size": block_size,
        "alpha": alpha,
        "samples": samples,
        "seed": seed,
    }


# ------------------------------------------------------------------- CSCV/PBO
def cscv_pbo(score_matrix, groups=16):
    """Probability of Backtest Overfailure via CSCV (Bailey et al. 2016).

    ``score_matrix``: list (strategies) of lists (time slices) of OOS scores.
    Slices are split into ``groups`` partitions; every combination of half the
    groups as training and the rest as testing is evaluated. PBO = fraction of
    splits where the train-best strategy ranks below the median OOS rank
    (logit-transformed relative rank, per the paper).

    Requires at least 2 strategies and ``groups`` >= 4 even.
    Returns ``None`` when the sample cannot support the estimate (M < 2).
    """
    m = len(score_matrix)
    if m < 2:
        return None
    t = min(len(row) for row in score_matrix)
    if t < groups or groups % 2 != 0:
        raise ValueError("need at least `groups` slices and an even group count")
    # trim rows to common length and slice evenly
    per_group = t // groups
    matrix = [[row[i * per_group:(i + 1) * per_group] for i in range(groups)]
              for row in score_matrix[:m]]
    matrix = [[sum(part) / max(len(part), 1) for part in row] for row in matrix]

    def _combos(pool, k):
        if k == 0:
            yield ()
            return
        for i in range(len(pool)):
            for rest in _combos(pool[i + 1:], k - 1):
                yield (pool[i],) + rest

    half = groups // 2
    logits = []
    for train_idx in _combos(list(range(groups)), half):
        test_idx = [g for g in range(groups) if g not in train_idx]
        train_mean = [_mean([matrix[s][g] for g in train_idx]) for s in range(m)]
        test_mean = [_mean([matrix[s][g] for g in test_idx]) for s in range(m)]
        best_train = max(range(m), key=lambda s: train_mean[s])
        # OOS ranking of all strategies (higher score = better)
        order = sorted(range(m), key=lambda s: test_mean[s])
        rank_best = order.index(best_train)  # 0 = worst OOS
        omega = (rank_best + 1) / (m + 1)    # avoid logit endpoints
        rs = _std(test_mean)
        if rs == 0:
            continue
        logits.append(math.log(omega / (1.0 - omega)))
    if not logits:
        return None
    positive = sum(1 for value in logits if value > 0)
    # PBO: share of combinations where IS-best was NOT above median OOS rank
    worse_than_median = sum(1 for value in logits if value <= 0)
    total = len(logits)
    return {
        "pbo": worse_than_median / total,
        "combinations": total,
        "strategies": m,
        "groups": groups,
    }
