"""Deterministic dataset partitioning via fraction list."""

from __future__ import annotations

import random
from typing import Any, Callable, Hashable, TypeVar

from pydantic import BaseModel

from ..benchmark.dataset import Dataset
from ..benchmark.entry import Entry
from .loader import _resolve_key


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


def stratified_split(
    dataset: Dataset[In, Out],
    fractions: list[float],
    key: Callable[[Entry[In, Out]], Hashable] | str,
    *,
    seed: int | None = None,
) -> list[Dataset[In, Out]]:
    """Split ``dataset`` into disjoint shards preserving per-class proportions.

    ``key`` is either a callable ``(Entry) -> Hashable`` or a dotted path
    string evaluated against ``entry.expected_output`` (e.g. ``"label"``).
    Fractions must be strictly positive and sum to 1.0 (± 1e-6). Children
    inherit ``dataset.version`` and receive ``name=f"{dataset.name}/split{i}"``.
    Single-key stratification only.
    """
    if not fractions:
        raise ValueError("fractions must be non-empty")
    if any(f <= 0 for f in fractions):
        raise ValueError("fractions must all be strictly positive")
    if abs(sum(fractions) - 1.0) > 1e-6:
        raise ValueError(
            f"fractions must sum to 1.0 (got {sum(fractions):.6f})"
        )

    key_fn = _resolve_key(key)
    rng = random.Random(seed)

    # Group indices by class
    buckets: dict[Hashable, list[int]] = {}
    for i, entry in enumerate(dataset):
        k = key_fn(entry)
        buckets.setdefault(k, []).append(i)

    # Shuffle and split each class bucket proportionally
    per_class_shards: list[list[int]] = [[] for _ in fractions]
    for lst in buckets.values():
        rng.shuffle(lst)
        n_cls = len(lst)
        sizes = [round(f * n_cls) for f in fractions[:-1]]
        sizes.append(n_cls - sum(sizes))
        cursor = 0
        for i, size in enumerate(sizes):
            per_class_shards[i].extend(lst[cursor : cursor + size])
            cursor += size

    shards: list[Dataset[In, Out]] = []
    for i, indices in enumerate(per_class_shards):
        shards.append(
            Dataset(
                entries=[dataset[k] for k in indices],
                name=f"{dataset.name}/split{i}",
                version=dataset.version,
            )
        )
    return shards


__all__ = ["random_split", "stratified_split"]
