"""StrandsRunner: composition replaces inheritance.

Regression coverage for the seam between operad and strands.
`Agent` no longer inherits from `strands.Agent`; default-forward
leaves hold a `StrandsRunner` constructed at build time.
"""

from __future__ import annotations

import pytest
import strands

from operad import Agent
from operad.core.runner import StrandsRunner

from .._helpers.fake_leaf import A, B, FakeLeaf
from .._helpers.spy_strands import StrandsSpy, install_spy

pytestmark = pytest.mark.asyncio


def test_agent_no_longer_inherits_strands_agent() -> None:
    assert strands.Agent not in Agent.__mro__


async def test_default_forward_leaf_holds_a_strands_runner(cfg) -> None:
    class Leaf(Agent[A, B]):
        input = A
        output = B
        role = "r"
        task = "t"

    leaf = await Leaf(config=cfg).abuild()
    assert isinstance(leaf._runner, StrandsRunner)
    assert leaf._runner.model is not None


async def test_custom_forward_leaf_has_no_runner(cfg) -> None:
    """FakeLeaf overrides forward, so the runner stays None."""
    leaf = await FakeLeaf(config=cfg, input=A, output=B).abuild()
    assert leaf._runner is None


async def test_no_strands_state_attribute_on_built_leaf(cfg) -> None:
    """Regression: the `_strands_state` workaround is gone for good."""

    class Leaf(Agent[A, B]):
        input = A
        output = B
        role = "r"
        task = "t"

    leaf = await Leaf(config=cfg).abuild()
    assert "_strands_state" not in leaf.__dict__
    # `state` remains a method, never replaced by a strands AgentState.
    assert "state" not in leaf.__dict__
    assert callable(leaf.state)


async def test_runner_invokes_strands_with_system_prompt(
    cfg, monkeypatch
) -> None:
    """End-to-end seam: composed system prompt reaches strands.Agent."""
    spy = install_spy(monkeypatch, StrandsSpy(canned_structured=B(value=1)))

    class Leaf(Agent[A, B]):
        input = A
        output = B
        role = "r"
        task = "t"

    leaf = await Leaf(config=cfg).abuild()
    await leaf(A(text="hi"))

    assert spy.calls, "runner should reach strands.Agent.invoke_async"
    # The transient strands.Agent constructed inside StrandsRunner
    # carries the per-call composed system prompt.
    assert any(sp for sp in spy.system_prompts)


async def test_runner_uses_native_structured_output_for_marked_models(
    cfg, monkeypatch
) -> None:
    """Marked providers bypass Strands' structured-output tool loop."""

    class Leaf(Agent[A, B]):
        input = A
        output = B
        role = "r"
        task = "t"

    leaf = await Leaf(config=cfg).abuild()
    assert leaf._runner is not None
    monkeypatch.setattr(
        type(leaf._runner.model),
        "_operad_native_structured_output",
        True,
        raising=False,
    )
    calls: list[tuple[type[B], str]] = []

    async def _fake_structured_output_async(
        self: object,
        output_model: type[B],
        prompt: str,
    ) -> B:
        calls.append((output_model, prompt))
        return B(value=7)

    async def _fail_invoke_async(*args: object, **kwargs: object) -> object:
        raise AssertionError("native path should not call invoke_async")

    monkeypatch.setattr(
        strands.Agent,
        "structured_output_async",
        _fake_structured_output_async,
    )
    monkeypatch.setattr(strands.Agent, "invoke_async", _fail_invoke_async)

    result = await leaf._runner.invoke_async("hello", structured_output_model=B)

    assert result.structured_output == B(value=7)
    assert calls == [(B, "hello")]
