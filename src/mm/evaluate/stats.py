"""Bootstrap confidence intervals and McNemar's test.

Bootstrap: 1,000 resamples with replacement, NumPy ``Generator`` seed, 2.5 and
97.5 percentiles of the resampled mean (linear quantile).

McNemar: exact two-sided binomial test on the first condition's discordant
count when the number of discordant pairs is under 25. Otherwise a chi-square
statistic ``(b - c) ** 2 / (b + c)`` with one degree of freedom and no
continuity correction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.stats import binomtest, chi2

N_RESAMPLES = 1000
DEFAULT_SEED = 0


@dataclass(frozen=True)
class MeanInterval:
    """Point estimate and a 95% bootstrap interval."""

    estimate: float
    low: float
    high: float


@dataclass(frozen=True)
class McNemarResult:
    """Paired comparison of two binary outcomes on the same examples."""

    p_value: float
    discordant: int
    method: str
    difference: float
    difference_low: float
    difference_high: float


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    n_resamples: int = N_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> MeanInterval:
    """Mean of ``values`` with a percentile bootstrap interval."""
    array = np.asarray(list(values), dtype=np.float64)
    if array.size == 0:
        return MeanInterval(estimate=float("nan"), low=float("nan"), high=float("nan"))
    estimate = float(array.mean())
    rng = np.random.default_rng(seed)
    means = np.empty(n_resamples, dtype=np.float64)
    for index in range(n_resamples):
        draw = rng.choice(array, size=array.size, replace=True)
        means[index] = draw.mean()
    low, high = np.quantile(means, [0.025, 0.975])
    return MeanInterval(estimate=estimate, low=float(low), high=float(high))


def bootstrap_difference_ci(
    left: Sequence[float],
    right: Sequence[float],
    *,
    n_resamples: int = N_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> MeanInterval:
    """Bootstrap interval for the mean of ``left - right`` on paired rows."""
    if len(left) != len(right):
        message = "paired comparison needs the same number of outcomes"
        raise ValueError(message)
    paired = [float(a) - float(b) for a, b in zip(left, right, strict=True)]
    return bootstrap_mean_ci(paired, n_resamples=n_resamples, seed=seed)


def mcnemar_test(
    left: Sequence[bool],
    right: Sequence[bool],
    *,
    n_resamples: int = N_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> McNemarResult:
    """McNemar p-value plus the difference in accuracy with a bootstrap interval."""
    if len(left) != len(right):
        message = "paired comparison needs the same number of outcomes"
        raise ValueError(message)
    first_only = 0
    second_only = 0
    for left_ok, right_ok in zip(left, right, strict=True):
        if left_ok and not right_ok:
            first_only += 1
        elif right_ok and not left_ok:
            second_only += 1
    discordant = first_only + second_only
    if discordant < 25:
        p_value = 1.0 if discordant == 0 else _exact_p(first_only, discordant)
        method = "exact-binomial"
    else:
        statistic = (first_only - second_only) ** 2 / discordant
        p_value = float(chi2.sf(statistic, 1))
        method = "chi-square"
    interval = bootstrap_difference_ci(
        [1.0 if value else 0.0 for value in left],
        [1.0 if value else 0.0 for value in right],
        n_resamples=n_resamples,
        seed=seed,
    )
    return McNemarResult(
        p_value=p_value,
        discordant=discordant,
        method=method,
        difference=interval.estimate,
        difference_low=interval.low,
        difference_high=interval.high,
    )


def accuracy_by_group(
    groups: Sequence[str],
    correct: Sequence[bool],
) -> dict[str, float]:
    """Mean of ``correct`` within each group label, such as difficulty."""
    if len(groups) != len(correct):
        message = "groups and outcomes must be the same length"
        raise ValueError(message)
    totals: dict[str, list[int]] = {}
    for group, flag in zip(groups, correct, strict=True):
        bucket = totals.setdefault(group, [0, 0])
        bucket[1] += 1
        if flag:
            bucket[0] += 1
    return {group: hits / count for group, (hits, count) in sorted(totals.items())}


def _exact_p(first_only: int, discordant: int) -> float:
    return float(binomtest(first_only, discordant, 0.5, alternative="two-sided").pvalue)
