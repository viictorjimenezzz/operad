"""Tests for ``Switch``: tracer-aware dispatch over a ``Router``'s choice."""

from __future__ import annotations

from typing import Any, Literal

import pytest

from operad import (
    Agent,
    BuildError,
    Choice,
    RouteInput,
    Router,
    Switch,
)
from tests.conftest import A, B


pytestmark = pytest.mark.asyncio


class Label(Choice[Literal["a", "b"]]):
    pass


class _StubRouter(Router):
    def __init__(self, *, label: str) -> None:
        super().__init__(config=None, input=A, output=Label)
        self._label = label

    async def forward(self, x: Any) -> Any:
        return Label.model_construct(label=self._label, reasoning="stub")


class _Branch(Agent[Any, Any]):
    def __init__(self, *, tag: str) -> None:
        super().__init__(config=None, input=A, output=B)
        self._tag = tag
        self.invocations: list[Any] = []

    async def forward(self, x: Any) -> Any:
        self.invocations.append(x)
        return B(value=1 if self._tag == "a" else 2)


def _build_switch(*, label: str) -> Switch:
    return Switch(
        router=_StubRouter(label=label),
        branches={"a": _Branch(tag="a"), "b": _Branch(tag="b")},
        input=A,
        output=B,
    )


async def test_switch_build_traces_router_and_every_branch() -> None:
    s = await _build_switch(label="a").abuild()
    callees = {e.callee for e in s._graph.edges}
    assert "Switch.router" in callees
    assert "Switch.branch_a" in callees
    assert "Switch.branch_b" in callees


async def test_switch_runtime_dispatches_to_selected_branch() -> None:
    s = await _build_switch(label="a").abuild()
    out = await s(A(text="x"))
    assert isinstance(out, B)
    assert out.value == 1
    assert len(s.branch_a.invocations) == 1  # type: ignore[attr-defined]
    assert s.branch_b.invocations == []  # type: ignore[attr-defined]

    s2 = await _build_switch(label="b").abuild()
    out2 = await s2(A(text="y"))
    assert out2.value == 2
    assert s2.branch_a.invocations == []  # type: ignore[attr-defined]
    assert len(s2.branch_b.invocations) == 1  # type: ignore[attr-defined]


async def test_switch_raises_router_miss_on_unknown_label() -> None:
    s = await _build_switch(label="zzz").abuild()
    with pytest.raises(BuildError) as excinfo:
        await s(A(text="x"))
    assert excinfo.value.reason == "router_miss"


async def test_switch_requires_at_least_one_branch() -> None:
    with pytest.raises(ValueError):
        Switch(
            router=_StubRouter(label="a"),
            branches={},
            input=A,
            output=B,
        )


async def test_switch_is_config_less_composite() -> None:
    s = _build_switch(label="a")
    assert s.config is None
    assert s._children  # composite
