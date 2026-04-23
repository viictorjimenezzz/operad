"""Tests for `Agent`: child tracking, invoke guards, and contract checks."""

from __future__ import annotations

import pytest

from operad import Agent, BuildError

from .conftest import A, B, C, BrokenOutputLeaf, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_assigning_agent_attribute_registers_child(cfg) -> None:
    class Composite(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.inner = FakeLeaf(config=cfg, input=A, output=B)

        async def forward(self, x: A) -> C:  # type: ignore[override]
            await self.inner(x)
            return C.model_construct()

    c = Composite()
    assert "inner" in c._children
    assert c._children["inner"] is c.inner


async def test_non_agent_attributes_do_not_pollute_children(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.some_string = "hello"  # type: ignore[attr-defined]
    leaf.some_dict = {"k": 1}  # type: ignore[attr-defined]
    assert leaf._children == {}


async def test_invoke_before_build_raises_not_built(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(BuildError) as exc:
        await leaf(A(text="hi"))
    assert exc.value.reason == "not_built"


async def test_invoke_with_wrong_input_type_raises_input_mismatch(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    with pytest.raises(BuildError) as exc:
        await leaf(B(value=1))  # wrong type: expected A
    assert exc.value.reason == "input_mismatch"


async def test_leaf_returning_wrong_type_raises_output_mismatch(cfg) -> None:
    leaf = BrokenOutputLeaf(
        config=cfg, input=A, output=B, wrong=C(label="nope")
    )
    with pytest.raises(BuildError) as exc:
        await leaf.abuild()
    assert exc.value.reason == "output_mismatch"


async def test_prompt_fields_mutable_before_build(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B, task="v1")
    leaf.task = "v2"
    leaf.config.temperature = 0.1
    await leaf.abuild()
    assert leaf.task == "v2"
    assert leaf.config.temperature == 0.1


async def test_invoke_after_build_returns_correct_type(cfg) -> None:
    leaf = await FakeLeaf(
        config=cfg, input=A, output=B, canned={"value": 42}
    ).abuild()
    out = await leaf(A(text="hi"))
    assert isinstance(out.response, B)
    assert out.response.value == 42


async def test_agent_is_built_flag_flips(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    assert leaf._built is False
    await leaf.abuild()
    assert leaf._built is True


async def test_build_from_inside_loop_raises_runtime_error(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    with pytest.raises(RuntimeError, match="running event loop"):
        leaf.build()
