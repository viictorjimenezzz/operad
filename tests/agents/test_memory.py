"""Tests for the memory extractor leaves."""

from __future__ import annotations
import pytest
from operad import Example
from operad.agents import Belief, BeliefExtractor, Beliefs, Conversation, EpisodicSummarizer, Summary, Turn, UserModel, UserModelExtractor
from pathlib import Path
from pydantic import BaseModel
from operad.agents import Belief, MemoryStore


# --- from test_memory_components.py ---
LEAF_SPECS = [
    (BeliefExtractor, Conversation, Beliefs),
    (UserModelExtractor, Conversation, UserModel),
    (EpisodicSummarizer, Conversation, Summary),
]


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_defaults_are_populated(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg)
    assert leaf.role, f"{cls.__name__}.role is empty"
    assert leaf.task, f"{cls.__name__}.task is empty"
    assert leaf.rules, f"{cls.__name__}.rules is empty"
    assert leaf.input is in_cls
    assert leaf.output is out_cls


@pytest.mark.parametrize("cls,in_cls,out_cls", LEAF_SPECS)
def test_leaf_ships_at_least_one_typed_example(cfg, cls, in_cls, out_cls) -> None:
    leaf = cls(config=cfg)
    assert leaf.examples, f"{cls.__name__} ships no examples"
    for ex in leaf.examples:
        assert isinstance(ex, Example)
        assert isinstance(ex.input, in_cls)
        assert isinstance(ex.output, out_cls)


@pytest.mark.parametrize("cls,_in,_out", LEAF_SPECS)
def test_leaf_task_override_wins(cfg, cls, _in, _out) -> None:
    leaf = cls(config=cfg, task="custom-task")
    assert leaf.task == "custom-task"


async def _patched(self, x):
    return self._canned


@pytest.mark.asyncio
async def test_belief_extractor_invoke_with_canned_forward(cfg) -> None:
    leaf = BeliefExtractor(config=cfg)
    leaf._canned = Beliefs(
        items=[
            Belief(
                subject="user",
                predicate="likes",
                object="jazz",
                confidence=0.8,
            ),
        ]
    )
    type(leaf).forward = _patched  # type: ignore[method-assign]
    try:
        await leaf.abuild()
        out = await leaf(Conversation(turns=[Turn(speaker="user", text="I love jazz.")]))
        assert isinstance(out.response, Beliefs)
        assert out.response.items[0].object == "jazz"
    finally:
        del type(leaf).forward


@pytest.mark.asyncio
async def test_user_model_extractor_invoke_with_canned_forward(cfg) -> None:
    leaf = UserModelExtractor(config=cfg)
    leaf._canned = UserModel(attributes={"name": "Ada"})
    type(leaf).forward = _patched  # type: ignore[method-assign]
    try:
        await leaf.abuild()
        out = await leaf(Conversation(turns=[Turn(speaker="user", text="I'm Ada.")]))
        assert isinstance(out.response, UserModel)
        assert out.response.attributes == {"name": "Ada"}
    finally:
        del type(leaf).forward


@pytest.mark.asyncio
async def test_episodic_summarizer_invoke_with_canned_forward(cfg) -> None:
    leaf = EpisodicSummarizer(config=cfg)
    leaf._canned = Summary(title="Hi", text="A short greeting.")
    type(leaf).forward = _patched  # type: ignore[method-assign]
    try:
        await leaf.abuild()
        out = await leaf(Conversation(turns=[Turn(speaker="user", text="hello")]))
        assert isinstance(out.response, Summary)
        assert out.response.title == "Hi"
    finally:
        del type(leaf).forward

# --- from test_memory_store.py ---
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
