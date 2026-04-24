"""Deterministic dataset partitioning via fraction list."""

from __future__ import annotations

import random
from typing import TypeVar

from pydantic import BaseModel

from ..benchmark.dataset import Dataset


In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


def random_split(
    dataset: Dataset[In, Out],
    fractions: list[float],
    *,
    seed: int | None = None,
) -> list[Dataset[In, Out]]:
    """Split `dataset` into disjoint shards sized by `fractions`.

    Fractions must be strictly positive and sum to 1.0 (± 1e-6). Children
    inherit `dataset.version` and receive `name=f"{dataset.name}/split{i}"`
    so `hash_dataset` is deterministic for a given `(origin, seed, fractions)`.
    Any rounding remainder is absorbed into the final shard to preserve
    the total entry count.
    """
    if not fractions:
        raise ValueError("fractions must be non-empty")
    if any(f <= 0 for f in fractions):
        raise ValueError("fractions must all be strictly positive")
    if abs(sum(fractions) - 1.0) > 1e-6:
        raise ValueError(
            f"fractions must sum to 1.0 (got {sum(fractions):.6f})"
        )

    n = len(dataset)
    order = list(range(n))
    random.Random(seed).shuffle(order)

    sizes = [round(f * n) for f in fractions[:-1]]
    sizes.append(n - sum(sizes))

    shards: list[Dataset[In, Out]] = []
    cursor = 0
    for i, size in enumerate(sizes):
        slice_indices = order[cursor : cursor + size]
        cursor += size
        shards.append(
            Dataset(
                entries=[dataset[k] for k in slice_indices],
                name=f"{dataset.name}/split{i}",
                version=dataset.version,
            )
        )
    return shards


__all__ = ["random_split"]
