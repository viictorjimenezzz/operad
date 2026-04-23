"""Tests for the memory extractor leaves."""

from __future__ import annotations

import pytest

from operad import (
    Belief,
    BeliefExtractor,
    Beliefs,
    Conversation,
    EpisodicSummarizer,
    Example,
    Summary,
    Turn,
    UserModel,
    UserModelExtractor,
)


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
        assert isinstance(out, Beliefs)
        assert out.items[0].object == "jazz"
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
        assert isinstance(out, UserModel)
        assert out.attributes == {"name": "Ada"}
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
        assert isinstance(out, Summary)
        assert out.title == "Hi"
    finally:
        del type(leaf).forward
