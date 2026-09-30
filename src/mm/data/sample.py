"""Stratified draws over difficulty and database id."""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from mm.data.bird import Example


def stratified_sample(
    examples: tuple[Example, ...] | list[Example], n: int | str, seed: int
) -> tuple[Example, ...]:
    """Draw ``n`` examples, or every example when ``n`` is ``all`` or larger than the set.

    Allocation is proportional to each ``(difficulty, db_id)`` group, with the
    largest remainders taking the leftover seats. Within a group the draw uses
    ``numpy`` Generator ``seed``.
    """
    ordered = tuple(sorted(examples, key=lambda example: example.question_id))
    if isinstance(n, str) or n >= len(ordered):
        return ordered
    groups: dict[tuple[str, str], list[Example]] = defaultdict(list)
    for example in ordered:
        groups[(example.difficulty.value, example.db_id)].append(example)
    keys = sorted(groups)
    sizes = [len(groups[key]) for key in keys]
    total = sum(sizes)
    raw = [n * size / total for size in sizes]
    counts = [int(value) for value in raw]
    leftover = n - sum(counts)
    remainders = sorted(
        range(len(keys)), key=lambda index: (raw[index] - counts[index], -index), reverse=True
    )
    for index in remainders[:leftover]:
        counts[index] += 1
    rng = np.random.default_rng(seed)
    chosen: list[Example] = []
    for key, count in zip(keys, counts, strict=True):
        pool = groups[key]
        if count >= len(pool):
            chosen.extend(pool)
            continue
        indexes = rng.choice(len(pool), size=count, replace=False)
        chosen.extend(pool[int(index)] for index in sorted(int(value) for value in indexes))
    return tuple(sorted(chosen, key=lambda example: example.question_id))
