"""Offline tests for `operad.data.random_split`."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.data import random_split


class _In(BaseModel):
    i: int


class _Out(BaseModel):
    i: int


def _make_dataset(n: int = 20, name: str = "parent", version: str = "v7") -> Dataset[_In, _Out]:
    entries = [Entry(input=_In(i=k), expected_output=_Out(i=k)) for k in range(n)]
    return Dataset(entries, name=name, version=version)


def _inputs(ds: Dataset[_In, _Out]) -> list[int]:
    return [e.input.i for e in ds]


def test_random_split_deterministic() -> None:
    ds = _make_dataset(20)
    a = [_inputs(shard) for shard in random_split(ds, [0.8, 0.2], seed=1)]
    b = [_inputs(shard) for shard in random_split(ds, [0.8, 0.2], seed=1)]
    assert a == b


def test_random_split_no_duplicates() -> None:
    ds = _make_dataset(20)
    shards = random_split(ds, [0.5, 0.3, 0.2], seed=7)
    flat = [i for shard in shards for i in _inputs(shard)]
    assert sorted(flat) == list(range(20))
    seen: set[int] = set()
    for shard in shards:
        ids = set(_inputs(shard))
        assert ids.isdisjoint(seen)
        seen |= ids


def test_random_split_bad_fractions_raise() -> None:
    ds = _make_dataset(10)
    with pytest.raises(ValueError):
        random_split(ds, [0.5, 0.4])
    with pytest.raises(ValueError):
        random_split(ds, [1.2, -0.2])
    with pytest.raises(ValueError):
        random_split(ds, [])


def test_random_split_names() -> None:
    ds = _make_dataset(10, name="parent", version="v7")
    shards = random_split(ds, [0.5, 0.5], seed=0)
    assert [s.name for s in shards] == ["parent/split0", "parent/split1"]
    assert all(s.version == "v7" for s in shards)
