"""Phase 2: bootstrap intervals and McNemar match hand-computed values."""

from __future__ import annotations

import pytest

from mm.evaluate.stats import accuracy_by_group, bootstrap_mean_ci, mcnemar_test

# Hand calculation for values [1, 0, 1, 1, 0], seed 0, 1,000 resamples.
# Mean = 3/5 = 0.6.
# NumPy Generator(0) draws, linear 2.5/97.5 percentiles: 0.2 and 1.0.
# Exact binomial: 0 successes in 5 trials, two-sided, p = 2/32 = 0.0625.
# Two discordant pairs split 1 and 1: two-sided p = 1.
# Chi-square with b=20, c=5: (20-5)^2 / 25 = 9, survival of chi-square(df=1).


def test_bootstrap_mean_matches_hand_computed_interval() -> None:
    interval = bootstrap_mean_ci([1, 0, 1, 1, 0], n_resamples=1000, seed=0)
    assert interval.estimate == pytest.approx(0.6)
    assert interval.low == pytest.approx(0.2)
    assert interval.high == pytest.approx(1.0)


def test_mcnemar_exact_and_chi_square_match_hand_computed_p_values() -> None:
    none_versus_all = mcnemar_test([False] * 5, [True] * 5, n_resamples=1000, seed=0)
    assert none_versus_all.discordant == 5
    assert none_versus_all.method == "exact-binomial"
    assert none_versus_all.p_value == pytest.approx(0.0625)
    assert none_versus_all.difference == pytest.approx(-1.0)

    balanced = mcnemar_test([True, False], [False, True], n_resamples=1000, seed=0)
    assert balanced.method == "exact-binomial"
    assert balanced.p_value == pytest.approx(1.0)
    assert balanced.difference == pytest.approx(0.0)

    left = [True] * 20 + [False] * 5
    right = [False] * 20 + [True] * 5
    large = mcnemar_test(left, right, n_resamples=1000, seed=0)
    assert large.discordant == 25
    assert large.method == "chi-square"
    assert large.p_value == pytest.approx(0.0026997960632601883)
    assert large.difference == pytest.approx(0.6)
    assert large.difference_low == pytest.approx(0.2)
    assert large.difference_high == pytest.approx(0.92)


def test_accuracy_by_difficulty_matches_hand_counts() -> None:
    grouped = accuracy_by_group(
        ["simple", "simple", "moderate"],
        [True, False, True],
    )
    assert grouped == {"moderate": 1.0, "simple": 0.5}
