"""Tests for the memory extractor leaves."""

from __future__ import annotations

import pytest

from operad import Example
from operad.agents import (
    BeliefItem,
    BeliefOperation,
    Beliefs,
    BeliefsInput,
    BeliefsOutput,
    User,
    UserInput,
    UserOutput,
)


LEAF_SPECS = [
    (Beliefs, BeliefsInput, BeliefsOutput),
    (User, UserInput, UserOutput),
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
async def test_beliefs_invoke_with_canned_forward(cfg) -> None:
    leaf = Beliefs(config=cfg)
    leaf._canned = BeliefsOutput(
        operations=[
            BeliefOperation(
                op="add",
                item=BeliefItem(
                    topic_key="user_music_preference",
                    claim_text="User likes jazz.",
                    salience_score=0.8,
                ),
                reason="Stated preference.",
            ),
        ],
        updated_summary="User likes jazz.",
    )
    type(leaf).forward = _patched  # type: ignore[method-assign]
    try:
        await leaf.abuild()
        out = await leaf(BeliefsInput(utterance="I love jazz."))
        assert isinstance(out.response, BeliefsOutput)
        assert out.response.operations[0].item is not None
        assert out.response.operations[0].item.claim_text == "User likes jazz."
    finally:
        del type(leaf).forward


@pytest.mark.asyncio
async def test_user_invoke_with_canned_forward(cfg) -> None:
    leaf = User(config=cfg)
    leaf._canned = UserOutput(operations=[])
    type(leaf).forward = _patched  # type: ignore[method-assign]
    try:
        await leaf.abuild()
        out = await leaf(UserInput(user_message="hello"))
        assert isinstance(out.response, UserOutput)
        assert out.response.operations == []
    finally:
        del type(leaf).forward
