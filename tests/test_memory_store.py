"""Tests for `MemoryStore[T]`."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from operad import Belief, MemoryStore


class _Note(BaseModel):
    text: str
    score: float = 0.0


def test_add_all_filter_roundtrip() -> None:
    store: MemoryStore[_Note] = MemoryStore(schema=_Note)
    store.add(_Note(text="a", score=0.9))
    store.add(_Note(text="b", score=0.3))
    store.add(_Note(text="c", score=0.7))

    assert len(store.all()) == 3
    high = store.filter(lambda n: n.score > 0.5)
    assert [n.text for n in high] == ["a", "c"]


def test_add_rejects_wrong_type() -> None:
    store: MemoryStore[_Note] = MemoryStore(schema=_Note)
    with pytest.raises(TypeError):
        store.add("not a note")  # type: ignore[arg-type]


def test_add_rejects_other_pydantic_type() -> None:
    store: MemoryStore[_Note] = MemoryStore(schema=_Note)
    with pytest.raises(TypeError):
        store.add(Belief(subject="x", predicate="y", object="z"))  # type: ignore[arg-type]


def test_persistence_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "notes.ndjson"
    s1: MemoryStore[_Note] = MemoryStore(schema=_Note, path=path)
    s1.add(_Note(text="first", score=0.1))
    s1.add(_Note(text="second", score=0.9))

    assert path.exists()
    assert path.read_text().strip().count("\n") == 1  # two lines

    s2: MemoryStore[_Note] = MemoryStore(schema=_Note, path=path)
    texts = [n.text for n in s2.all()]
    assert texts == ["first", "second"]


def test_init_with_missing_path_is_ok(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "missing.ndjson"
    store: MemoryStore[_Note] = MemoryStore(schema=_Note, path=path)
    assert store.all() == []
    store.add(_Note(text="hi"))
    assert path.exists()


def test_flush_rewrites_file(tmp_path: Path) -> None:
    path = tmp_path / "notes.ndjson"
    store: MemoryStore[_Note] = MemoryStore(schema=_Note, path=path)
    store.add(_Note(text="a"))
    store.add(_Note(text="b"))

    # Drop one item via direct mutation, then flush.
    store._items.pop(0)
    store.flush()

    s2: MemoryStore[_Note] = MemoryStore(schema=_Note, path=path)
    assert [n.text for n in s2.all()] == ["b"]


def test_flush_without_path_is_noop() -> None:
    store: MemoryStore[_Note] = MemoryStore(schema=_Note)
    store.add(_Note(text="x"))
    store.flush()
    assert [n.text for n in store.all()] == ["x"]
