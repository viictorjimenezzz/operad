"""Offline tests for `Agent.register_forward_pre_hook`,
`register_forward_hook`, and `register_backward_hook`.
"""

from __future__ import annotations

from typing import Any

import pytest

from operad import Configuration
from operad.core.flow import Sequential
from operad.optim import inference_mode, no_grad

from tests._helpers.fake_leaf import A, B, FakeLeaf


def _leaf(cfg: Configuration, **kw) -> FakeLeaf:
    return FakeLeaf(config=cfg, input=A, output=B, **kw)


@pytest.mark.asyncio
async def test_register_forward_pre_hook_mutates_input(cfg: Configuration) -> None:
    seen_by_forward: list[str] = []

    class RecordingLeaf(FakeLeaf):
        async def forward(self, x: Any) -> Any:
            seen_by_forward.append(x.text)
            return self.output.model_construct(**self.canned)

    leaf = RecordingLeaf(config=cfg, input=A, output=B)

    def pre(agent: Any, x: A) -> A:
        return A(text=x.text + "-pre")

    leaf.register_forward_pre_hook(pre)
    await leaf.abuild()
    seen_by_forward.clear()  # drop the sentinel observation from tracing
    await leaf.invoke(A(text="raw"))
    assert seen_by_forward == ["raw-pre"]


@pytest.mark.asyncio
async def test_forward_pre_hook_none_keeps_input(cfg: Configuration) -> None:
    seen: list[str] = []

    class RecordingLeaf(FakeLeaf):
        async def forward(self, x: Any) -> Any:
            seen.append(x.text)
            return self.output.model_construct()

    leaf = RecordingLeaf(config=cfg, input=A, output=B)

    def pre(agent: Any, x: A) -> None:
        return None

    leaf.register_forward_pre_hook(pre)
    await leaf.abuild()
    seen.clear()
    await leaf.invoke(A(text="keep"))
    assert seen == ["keep"]


@pytest.mark.asyncio
async def test_register_forward_hook_sees_output(cfg: Configuration) -> None:
    leaf = _leaf(cfg, canned={"value": 42})
    captured: list[tuple[Any, Any, Any]] = []

    def post(agent: Any, x: Any, y: Any) -> None:
        captured.append((agent, x, y))

    leaf.register_forward_hook(post)
    await leaf.abuild()
    await leaf.invoke(A(text="x"))
    assert len(captured) == 1
    agent, x, y = captured[0]
    assert agent is leaf
    assert x.text == "x"
    assert y.value == 42


@pytest.mark.asyncio
async def test_pre_hook_runs_before_forward_in(cfg: Configuration) -> None:
    order: list[str] = []

    class OrderedLeaf(FakeLeaf):
        def forward_in(self, x: Any) -> Any:
            order.append("forward_in")
            return x

        async def forward(self, x: Any) -> Any:
            order.append("forward")
            return self.output.model_construct()

    leaf = OrderedLeaf(config=cfg, input=A, output=B)
    leaf.register_forward_pre_hook(lambda a, x: order.append("pre") or None)
    await leaf.abuild()
    order.clear()
    await leaf.invoke(A(text=""))
    assert order == ["pre", "forward_in", "forward"]


@pytest.mark.asyncio
async def test_post_hook_runs_after_forward_out(cfg: Configuration) -> None:
    order: list[str] = []

    class OrderedLeaf(FakeLeaf):
        async def forward(self, x: Any) -> Any:
            order.append("forward")
            return self.output.model_construct()

        def forward_out(self, x: Any, y: Any) -> Any:
            order.append("forward_out")
            return y

    leaf = OrderedLeaf(config=cfg, input=A, output=B)
    leaf.register_forward_hook(lambda a, x, y: order.append("post"))
    await leaf.abuild()
    order.clear()
    await leaf.invoke(A(text=""))
    assert order == ["forward", "forward_out", "post"]


@pytest.mark.asyncio
async def test_handle_remove_unregisters(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    fired: list[bool] = []
    h = leaf.register_forward_hook(lambda a, x, y: fired.append(True))
    h.remove()
    await leaf.abuild()
    await leaf.invoke(A(text=""))
    assert fired == []


@pytest.mark.asyncio
async def test_handle_double_remove_is_noop(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    h = leaf.register_forward_hook(lambda a, x, y: None)
    h.remove()
    h.remove()  # second remove must not raise


@pytest.mark.asyncio
async def test_multiple_hooks_fire_in_registration_order(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    order: list[str] = []
    leaf.register_forward_hook(lambda a, x, y: order.append("one"))
    leaf.register_forward_hook(lambda a, x, y: order.append("two"))
    leaf.register_forward_hook(lambda a, x, y: order.append("three"))
    await leaf.abuild()
    await leaf.invoke(A(text=""))
    assert order == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_hook_remove_during_iteration_is_safe(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    fired: list[str] = []

    h2: list[Any] = []

    def first(a: Any, x: Any, y: Any) -> None:
        fired.append("first")
        h2[0].remove()

    def second(a: Any, x: Any, y: Any) -> None:
        fired.append("second")

    leaf.register_forward_hook(first)
    h2.append(leaf.register_forward_hook(second))
    await leaf.abuild()
    await leaf.invoke(A(text=""))
    # Both fire on first invocation (tuple snapshot).
    assert fired == ["first", "second"]
    fired.clear()
    await leaf.invoke(A(text=""))
    # Second has been removed for subsequent invocations.
    assert fired == ["first"]


@pytest.mark.asyncio
async def test_inference_mode_skips_all_hooks(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    fired: list[str] = []
    leaf.register_forward_pre_hook(lambda a, x: fired.append("pre") or None)
    leaf.register_forward_hook(lambda a, x, y: fired.append("post"))
    await leaf.abuild()
    async with inference_mode():
        await leaf.invoke(A(text=""))
    assert fired == []


@pytest.mark.asyncio
async def test_no_grad_does_not_skip_hooks(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    fired: list[str] = []
    leaf.register_forward_pre_hook(lambda a, x: fired.append("pre") or None)
    leaf.register_forward_hook(lambda a, x, y: fired.append("post"))
    await leaf.abuild()
    async with no_grad():
        await leaf.invoke(A(text=""))
    assert fired == ["pre", "post"]


@pytest.mark.asyncio
async def test_tracer_bypasses_hooks(cfg: Configuration) -> None:
    """`build()` uses a tracer that short-circuits `invoke` before hooks run."""
    leaf = _leaf(cfg)
    fired: list[str] = []
    leaf.register_forward_pre_hook(lambda a, x: fired.append("pre") or None)
    leaf.register_forward_hook(lambda a, x, y: fired.append("post"))
    await leaf.abuild()
    assert fired == []


@pytest.mark.asyncio
async def test_backward_hook_is_stored(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    fn = lambda a, g: None  # noqa: E731
    h = leaf.register_backward_hook(fn)
    assert fn in leaf._backward_hooks
    h.remove()
    assert fn not in leaf._backward_hooks


@pytest.mark.asyncio
async def test_clone_resets_hook_lists(cfg: Configuration) -> None:
    leaf = _leaf(cfg)
    leaf.register_forward_pre_hook(lambda a, x: None)
    leaf.register_forward_hook(lambda a, x, y: None)
    leaf.register_backward_hook(lambda a, g: None)
    cloned = leaf.clone()
    assert cloned._forward_pre_hooks == []
    assert cloned._forward_hooks == []
    assert cloned._backward_hooks == []


@pytest.mark.asyncio
async def test_clone_composite_resets_hook_lists(cfg: Configuration) -> None:
    a, b = _leaf(cfg), _leaf(cfg)
    pipe = Sequential(a, b, input=A, output=B)
    pipe.register_forward_hook(lambda ag, x, y: None)
    a.register_forward_hook(lambda ag, x, y: None)
    cloned = pipe.clone()
    assert cloned._forward_hooks == []
    for child in cloned._children.values():
        assert child._forward_hooks == []
        assert child._forward_pre_hooks == []


@pytest.mark.asyncio
async def test_composite_hooks_fire_separately_from_children(cfg: Configuration) -> None:
    a = FakeLeaf(config=cfg, input=A, output=A)
    b = FakeLeaf(config=cfg, input=A, output=A)
    pipe = Sequential(a, b, input=A, output=A)
    fired: list[str] = []
    pipe.register_forward_hook(lambda ag, x, y: fired.append("pipe"))
    a.register_forward_hook(lambda ag, x, y: fired.append("a"))
    b.register_forward_hook(lambda ag, x, y: fired.append("b"))
    await pipe.abuild()
    fired.clear()
    await pipe.invoke(A(text=""))
    # Stage order is a -> b -> pipe (pipe's post-hook runs after its own forward).
    assert fired == ["a", "b", "pipe"]
