"""Async, deterministic batching over a typed `Dataset`.

This module provides the primitives `Trainer.fit()` iterates over:

- `Batch[In, Out]` — one unit of work, carrying typed inputs, expected
  outputs, per-row metric overrides, and stable hashes for cassette
  lookups.
- `Sampler` / `SequentialSampler` / `RandomSampler` / `WeightedRandomSampler`
  — how indices flow into `DataLoader`.
- `DataLoader[In, Out]` — async iterator yielding `Batch` objects from a
  `Dataset`.
"""

from __future__ import annotations

import asyncio
import math
import random
import time
import warnings
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Generic,
    Hashable,
    Iterator,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict

from ..benchmark.dataset import Dataset
from ..benchmark.entry import Entry
from ..metrics.base import Metric
from ..runtime.events import get_current_epoch
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
from ..utils.hashing import hash_json


_DATALOADER_PATH = "DataLoader"


In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Batch(BaseModel, Generic[In, Out]):
    """Typed slice of a dataset; one unit of work for `Trainer`."""

    inputs: list[In]
    expected: list[Out | None]
    metrics: list[Metric | None]
    indices: list[int]
    batch_id: str
    hash_batch: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


@runtime_checkable
class Sampler(Protocol):
    """Iterable of integer indices with a known length."""

    def __iter__(self) -> Iterator[int]: ...

    def __len__(self) -> int: ...


class SequentialSampler:
    """Yields `0, 1, ..., n-1` in order."""

    def __init__(self, n: int) -> None:
        if n < 0:
            raise ValueError("SequentialSampler length must be non-negative")
        self._n = n

    def __iter__(self) -> Iterator[int]:
        return iter(range(self._n))

    def __len__(self) -> int:
        return self._n


class RandomSampler:
    """Shuffles `range(n)` with a local RNG; seed reproduces order."""

    def __init__(self, n: int, *, seed: int | None = None) -> None:
        if n < 0:
            raise ValueError("RandomSampler length must be non-negative")
        self._n = n
        self._seed = seed

    def __iter__(self) -> Iterator[int]:
        rng = random.Random(self._seed)
        order = list(range(self._n))
        rng.shuffle(order)
        return iter(order)

    def __len__(self) -> int:
        return self._n


class WeightedRandomSampler:
    """Draws `num_samples` indices with replacement, weighted."""

    def __init__(
        self,
        weights: list[float],
        num_samples: int,
        *,
        seed: int | None = None,
    ) -> None:
        if not weights:
            raise ValueError("WeightedRandomSampler weights must be non-empty")
        if any(w < 0 for w in weights):
            raise ValueError("WeightedRandomSampler weights must be non-negative")
        if sum(weights) <= 0:
            raise ValueError("WeightedRandomSampler weights must sum to > 0")
        if num_samples < 0:
            raise ValueError("WeightedRandomSampler num_samples must be >= 0")
        self._weights = list(weights)
        self._num_samples = num_samples
        self._seed = seed

    def __iter__(self) -> Iterator[int]:
        rng = random.Random(self._seed)
        picks = rng.choices(
            range(len(self._weights)),
            weights=self._weights,
            k=self._num_samples,
        )
        return iter(picks)

    def __len__(self) -> int:
        return self._num_samples


def _resolve_key(
    key: Callable[..., Hashable] | str,
) -> Callable[..., Hashable]:
    if callable(key):
        return key
    parts = key.split(".")

    def _get(entry: Any) -> Hashable:
        obj = entry.expected_output
        for p in parts:
            obj = getattr(obj, p)
        return obj  # type: ignore[return-value]

    return _get


def _stratified_interleave(
    buckets: dict[Hashable, list[int]],
    n: int,
) -> Iterator[int]:
    classes = list(buckets.keys())
    counts = {k: len(v) for k, v in buckets.items()}
    pointers = {k: 0 for k in classes}
    deficit = {k: counts[k] / n for k in classes}
    for _ in range(n):
        cls = max(classes, key=lambda k: deficit[k])
        lst = buckets[cls]
        yield lst[pointers[cls] % len(lst)]
        pointers[cls] += 1
        for k in classes:
            deficit[k] += counts[k] / n
        deficit[cls] -= 1.0


class StratifiedSampler:
    """Yields indices preserving per-class frequency in each batch.

    ``key`` is either a callable ``(Entry) -> Hashable`` or a dotted path
    string evaluated against ``entry.expected_output`` (e.g. ``"label"``).
    Single-key stratification only.
    """

    def __init__(
        self,
        dataset: "Dataset[Any, Any]",
        key: Callable[..., Hashable] | str,
        batch_size: int | None = None,
        shuffle: bool = True,
        seed: int | None = None,
    ) -> None:
        self._dataset = dataset
        self._key_fn = _resolve_key(key)
        self._batch_size = batch_size
        self._shuffle = shuffle
        self._seed = seed

    def __iter__(self) -> Iterator[int]:
        rng = random.Random(self._seed)

        buckets: dict[Hashable, list[int]] = {}
        for i, entry in enumerate(self._dataset):
            k = self._key_fn(entry)
            buckets.setdefault(k, []).append(i)

        if self._shuffle:
            for lst in buckets.values():
                rng.shuffle(lst)

        bs = self._batch_size
        if bs is not None:
            for cls, lst in buckets.items():
                if len(lst) < bs:
                    warnings.warn(
                        f"StratifiedSampler: class {cls!r} has {len(lst)} samples "
                        f"< batch_size={bs}; oversampling within batch.",
                        UserWarning,
                        stacklevel=2,
                    )
                    break

        yield from _stratified_interleave(buckets, len(self._dataset))

    def __len__(self) -> int:
        return len(self._dataset)


class PermutableSampler:
    """Sampler that yields a caller-supplied index permutation.

    Call ``set_order(indices)`` before the next epoch to control exactly
    which dataset indices are visited and in what order. Until the first
    call, it yields ``0, 1, ..., n-1`` sequentially.
    """

    def __init__(self, n: int) -> None:
        if n < 0:
            raise ValueError("PermutableSampler length must be non-negative")
        self._order: list[int] = list(range(n))

    def set_order(self, indices: list[int]) -> None:
        """Replace the iteration order for the next epoch."""
        self._order = list(indices)

    def __iter__(self) -> Iterator[int]:
        return iter(self._order)

    def __len__(self) -> int:
        return len(self._order)


class DataLoader(Generic[In, Out]):
    """Async, deterministic iterator over `Batch` objects."""

    def __init__(
        self,
        dataset: Dataset[In, Out],
        *,
        batch_size: int = 1,
        shuffle: bool = False,
        drop_last: bool = False,
        num_workers: int = 0,
        sampler: Sampler | None = None,
        seed: int | None = None,
        collate_fn: Callable[[list[Entry[In, Out]]], Any] | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if num_workers < 0:
            raise ValueError("num_workers must be >= 0")
        if sampler is not None and shuffle:
            raise ValueError("sampler and shuffle=True are mutually exclusive")

        self._dataset = dataset
        self._batch_size = batch_size
        self._shuffle = shuffle
        self._drop_last = drop_last
        self._num_workers = num_workers
        self._sampler = sampler
        self._seed = seed
        self._collate_fn = collate_fn

    def __len__(self) -> int:
        n = len(self._sampler) if self._sampler is not None else len(self._dataset)
        if self._drop_last:
            return n // self._batch_size
        return math.ceil(n / self._batch_size)

    def _index_iter(self) -> Iterator[int]:
        if self._sampler is not None:
            return iter(self._sampler)
        if self._shuffle:
            return iter(RandomSampler(len(self._dataset), seed=self._seed))
        return iter(SequentialSampler(len(self._dataset)))

    def __aiter__(self) -> AsyncIterator[Any]:
        return _DataLoaderIter(self, self._index_iter())


class _DataLoaderIter(Generic[In, Out]):
    def __init__(
        self,
        loader: DataLoader[In, Out],
        indices: Iterator[int],
    ) -> None:
        self._loader = loader
        self._indices = indices
        self._batch_index = 0
        # (batch_index, batch_size, started_at) while a batch is in flight.
        self._pending: tuple[int, int, float] | None = None

    def __aiter__(self) -> "_DataLoaderIter[In, Out]":
        return self

    async def __anext__(self) -> Any:
        loader = self._loader
        await self._flush_pending()

        chunk: list[int] = []
        for _ in range(loader._batch_size):
            try:
                chunk.append(next(self._indices))
            except StopIteration:
                break
        if not chunk:
            raise StopAsyncIteration
        if loader._drop_last and len(chunk) < loader._batch_size:
            raise StopAsyncIteration

        entries = [loader._dataset[i] for i in chunk]
        batch = _default_collate(loader._dataset, chunk, entries)

        collate = loader._collate_fn
        if collate is not None:
            # Why: num_workers>0 offloads user-supplied collate off the event
            # loop. The brief mentions SandboxPool but its API (tool-class
            # dispatch, JSON round-trip, POSIX-only) is a poor fit for generic
            # collate work; to_thread preserves the parameter surface without
            # those constraints.
            if loader._num_workers > 0:
                result: Any = await asyncio.to_thread(collate, entries)
            else:
                result = collate(entries)
            hash_batch = ""
        else:
            result = batch
            hash_batch = batch.hash_batch

        await self._emit_batch_start(
            batch_size=len(chunk), hash_batch=hash_batch
        )
        self._pending = (self._batch_index, len(chunk), time.monotonic())
        self._batch_index += 1
        return result

    async def _emit_batch_start(
        self, *, batch_size: int, hash_batch: str
    ) -> None:
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "batch_start",
                algorithm_path=_DATALOADER_PATH,
                payload={
                    "batch_index": self._batch_index,
                    "batch_size": batch_size,
                    "hash_batch": hash_batch,
                    "epoch": get_current_epoch(),
                },
            )

    async def _flush_pending(self) -> None:
        if self._pending is None:
            return
        idx, size, started = self._pending
        self._pending = None
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "batch_end",
                algorithm_path=_DATALOADER_PATH,
                payload={
                    "batch_index": idx,
                    "batch_size": size,
                    "duration_ms": (time.monotonic() - started) * 1000.0,
                    "epoch": get_current_epoch(),
                },
            )


def _default_collate(
    dataset: Dataset[Any, Any],
    indices: list[int],
    entries: list[Entry[Any, Any]],
) -> Batch[Any, Any]:
    inputs = [e.input for e in entries]
    expected = [e.expected_output for e in entries]
    metrics = [e.metric for e in entries]
    payloads = [inp.model_dump(mode="json") for inp in inputs]
    hash_batch = hash_json(payloads)
    batch_id = hash_json(
        {"dataset": dataset.hash_dataset, "indices": list(indices)}
    )
    return Batch(
        inputs=inputs,
        expected=expected,
        metrics=metrics,
        indices=list(indices),
        batch_id=batch_id,
        hash_batch=hash_batch,
    )


__all__ = [
    "Batch",
    "DataLoader",
    "PermutableSampler",
    "RandomSampler",
    "Sampler",
    "SequentialSampler",
    "StratifiedSampler",
    "WeightedRandomSampler",
]
