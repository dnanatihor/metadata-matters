"""Recall, full coverage, MRR, and nDCG for a ranked list of schema objects."""

from __future__ import annotations

import math
from collections.abc import Sequence


def recall_at_k(gold: Sequence[str], ranking: Sequence[str], k: int) -> float:
    """Fraction of gold columns (or other items) present in the top ``k``."""
    if not gold:
        return 0.0
    found = set(ranking[:k]) & set(gold)
    return len(found) / len(set(gold))


def full_coverage_at_k(gold: Sequence[str], ranking: Sequence[str], k: int) -> float:
    """1 when every gold item is inside the top ``k``, otherwise 0."""
    if not gold:
        return 0.0
    return 1.0 if set(gold) <= set(ranking[:k]) else 0.0


def reciprocal_rank(gold: Sequence[str], ranking: Sequence[str]) -> float:
    """1 / rank of the first gold item. 0 when no gold item is ranked."""
    gold_set = set(gold)
    for index, item in enumerate(ranking, start=1):
        if item in gold_set:
            return 1.0 / index
    return 0.0


def ndcg_at_k(gold: Sequence[str], ranking: Sequence[str], k: int) -> float:
    """Binary nDCG@k. An empty gold set is 0."""
    relevant = set(gold)
    if not relevant:
        return 0.0
    ideal_hits = min(k, len(relevant))
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    if ideal == 0:
        return 0.0
    discount = 0.0
    for index, item in enumerate(ranking[:k], start=1):
        if item in relevant:
            discount += 1.0 / math.log2(index + 1)
    return discount / ideal
