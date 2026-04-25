"""Offline tests for `StratifiedSampler` and `stratified_split`."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.data import StratifiedSampler, stratified_split


class _In(BaseModel):
    i: int


class _Out(BaseModel):
    label: str


def _make_imbalanced(n_a: int = 80, n_b: int = 20) -> Dataset[_In, _Out]:
    entries = [
        Entry(input=_In(i=k), expected_output=_Out(label="A")) for k in range(n_a)
    ] + [
        Entry(input=_In(i=n_a + k), expected_output=_Out(label="B")) for k in range(n_b)
    ]
    return Dataset(entries, name="imbalanced", version="v1")


def _label(entry: Entry[_In, _Out]) -> str:
    assert entry.expected_output is not None
    return entry.expected_output.label


def _class_counts(indices: list[int], dataset: Dataset[_In, _Out]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for i in indices:
        lbl = dataset[i].expected_output.label  # type: ignore[union-attr]
        counts[lbl] = counts.get(lbl, 0) + 1
    return counts


def test_stratified_sampler_total_indices() -> None:
    ds = _make_imbalanced()
    sampler = StratifiedSampler(ds, key=_label, batch_size=10, seed=0)
    assert len(list(sampler)) == len(ds)
    assert len(sampler) == len(ds)


def test_stratified_sampler_batch_ratio() -> None:
    """Each batch of 10 should have ~8 A's and ~2 B's (within rounding ±1)."""
    ds = _make_imbalanced(80, 20)
    sampler = StratifiedSampler(ds, key=_label, batch_size=10, seed=42)
    indices = list(sampler)
    batch_size = 10
    for start in range(0, len(indices), batch_size):
        batch = indices[start : start + batch_size]
        counts = _class_counts(batch, ds)
        assert abs(counts.get("A", 0) - 8) <= 1
        assert abs(counts.get("B", 0) - 2) <= 1


def test_stratified_sampler_deterministic() -> None:
    ds = _make_imbalanced()
    a = list(StratifiedSampler(ds, key=_label, seed=7))
    b = list(StratifiedSampler(ds, key=_label, seed=7))
    assert a == b


def test_stratified_sampler_dotted_path() -> None:
    ds = _make_imbalanced()
    sampler_callable = StratifiedSampler(ds, key=_label, seed=3)
    sampler_dotted = StratifiedSampler(ds, key="label", seed=3)
    assert list(sampler_callable) == list(sampler_dotted)


def test_stratified_split_ratios() -> None:
    """Both halves of an 80/20 split must preserve the 80/20 class ratio."""
    ds = _make_imbalanced(80, 20)
    train, val = stratified_split(ds, [0.8, 0.2], key=_label, seed=0)

    def _ratio(shard: Dataset[_In, _Out]) -> float:
        a = sum(1 for e in shard if e.expected_output.label == "A")  # type: ignore[union-attr]
        return a / len(shard)

    # Original ratio is 0.8; each split should be within 5 percentage points.
    assert abs(_ratio(train) - 0.8) < 0.05
    assert abs(_ratio(val) - 0.8) < 0.05


def test_stratified_split_no_duplicates() -> None:
    ds = _make_imbalanced(80, 20)
    shards = stratified_split(ds, [0.7, 0.2, 0.1], key=_label, seed=1)
    all_inputs = [e.input.i for shard in shards for e in shard]
    assert sorted(all_inputs) == sorted(e.input.i for e in ds)
    assert len(set(all_inputs)) == len(all_inputs)


def test_stratified_split_bad_fractions() -> None:
    ds = _make_imbalanced(10, 10)
    with pytest.raises(ValueError):
        stratified_split(ds, [0.5, 0.4], key=_label)
    with pytest.raises(ValueError):
        stratified_split(ds, [1.2, -0.2], key=_label)
    with pytest.raises(ValueError):
        stratified_split(ds, [], key=_label)
