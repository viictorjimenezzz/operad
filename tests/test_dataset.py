"""Tests for the typed `Dataset[In, Out]` primitive."""

from __future__ import annotations

from pathlib import Path

from operad import Dataset

from .conftest import A, B


def _rows() -> list[tuple[A, B]]:
    return [(A(text="q1"), B(value=1)), (A(text="q2"), B(value=2))]


def test_construct_and_protocol() -> None:
    ds = Dataset(_rows(), name="t", version="v1")
    assert len(ds) == 2
    assert ds[0] == (A(text="q1"), B(value=1))
    assert list(iter(ds)) == _rows()


def test_hash_stable_across_reconstruction() -> None:
    a = Dataset(_rows(), name="t", version="v1")
    b = Dataset(_rows(), name="t", version="v1")
    assert a.hash_dataset == b.hash_dataset


def test_hash_changes_with_name_or_version() -> None:
    base = Dataset(_rows(), name="t", version="v1").hash_dataset
    assert Dataset(_rows(), name="t", version="v2").hash_dataset != base
    assert Dataset(_rows(), name="other", version="v1").hash_dataset != base


def test_save_load_roundtrip(tmp_path: Path) -> None:
    ds = Dataset(_rows(), name="t", version="v1")
    path = tmp_path / "ds.ndjson"
    ds.save(path)

    loaded = Dataset.load(path, in_cls=A, out_cls=B, name="t", version="v1")
    assert len(loaded) == len(ds)
    assert list(loaded) == list(ds)
    assert loaded.hash_dataset == ds.hash_dataset
