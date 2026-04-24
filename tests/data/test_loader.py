"""Offline tests for `operad.data.DataLoader` and the shipped samplers."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.data import Batch, DataLoader


class _In(BaseModel):
    i: int


class _Out(BaseModel):
    i: int


class _StubMetric:
    name: str = "stub"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        return 0.0

    async def score_batch(
        self, pairs: list[tuple[BaseModel, BaseModel]]
    ) -> list[float]:
        return [0.0] * len(pairs)


def _make_dataset(n: int = 10, name: str = "ds", version: str = "v1") -> Dataset[_In, _Out]:
    entries = [Entry(input=_In(i=k), expected_output=_Out(i=k)) for k in range(n)]
    return Dataset(entries, name=name, version=version)


async def _collect(loader: DataLoader[_In, _Out]) -> list[Batch[_In, _Out]]:
    return [b async for b in loader]


async def test_batch_count_ceil() -> None:
    ds = _make_dataset(10)
    loader = DataLoader(ds, batch_size=4)
    batches = await _collect(loader)
    assert len(batches) == 3
    assert len(loader) == 3
    assert [len(b.inputs) for b in batches] == [4, 4, 2]


async def test_drop_last_drops_partial() -> None:
    ds = _make_dataset(10)
    loader = DataLoader(ds, batch_size=4, drop_last=True)
    batches = await _collect(loader)
    assert len(batches) == 2
    assert len(loader) == 2
    assert all(len(b.inputs) == 4 for b in batches)


async def test_shuffle_seed_reproducible() -> None:
    ds = _make_dataset(10)
    loader = DataLoader(ds, batch_size=3, shuffle=True, seed=42)
    first = [b.indices for b in await _collect(loader)]
    second = [b.indices for b in await _collect(loader)]
    assert first == second
    # Shuffle actually reorders (not trivially equal to range).
    flat = [i for idx in first for i in idx]
    assert flat != list(range(10))


async def test_shuffle_different_seeds_differ() -> None:
    ds = _make_dataset(10)
    a = [b.indices for b in await _collect(DataLoader(ds, batch_size=3, shuffle=True, seed=1))]
    b = [b.indices for b in await _collect(DataLoader(ds, batch_size=3, shuffle=True, seed=2))]
    assert a != b


async def test_num_workers_zero_sequential() -> None:
    ds = _make_dataset(10)
    loader = DataLoader(ds, batch_size=3, num_workers=0)
    batches = await _collect(loader)
    collected = [i for b in batches for i in b.indices]
    assert collected == list(range(10))


async def test_num_workers_two_smoke() -> None:
    ds = _make_dataset(10)

    def collate(entries: list[Entry[_In, _Out]]) -> list[int]:
        return [e.input.i for e in entries]

    loader = DataLoader(ds, batch_size=3, num_workers=2, collate_fn=collate)
    results = [r async for r in loader]
    flat = [i for r in results for i in r]
    assert set(flat) == set(range(10))
    assert len(results) == 4


async def test_hash_batch_stable_for_equal_inputs() -> None:
    ds_a = _make_dataset(4, name="a", version="v1")
    ds_b = _make_dataset(4, name="b", version="v2")
    batches_a = await _collect(DataLoader(ds_a, batch_size=2))
    batches_b = await _collect(DataLoader(ds_b, batch_size=2))
    assert [b.hash_batch for b in batches_a] == [b.hash_batch for b in batches_b]
    assert [b.batch_id for b in batches_a] != [b.batch_id for b in batches_b]


def test_sampler_and_shuffle_conflict_raises() -> None:
    from operad.data import SequentialSampler

    ds = _make_dataset(4)
    with pytest.raises(ValueError):
        DataLoader(ds, batch_size=2, shuffle=True, sampler=SequentialSampler(4))


async def test_metric_override_preserved() -> None:
    metric = _StubMetric()
    entries = [Entry(input=_In(i=k), expected_output=_Out(i=k), metric=metric) for k in range(4)]
    ds: Dataset[_In, _Out] = Dataset(entries, name="m", version="v1")
    batches = await _collect(DataLoader(ds, batch_size=2))
    for b in batches:
        assert len(b.metrics) == len(b.inputs)
        assert all(m is metric for m in b.metrics)
