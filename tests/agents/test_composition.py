"""End-to-end composition tests.

These exercise the full build -> invoke path using FakeLeaf (no LLM) to
confirm that the framework behaves correctly for the three shapes we
expect users to build first: linear pipelines, fan-out, and nested
composites.
"""

from __future__ import annotations
import asyncio
import pytest
from operad import Agent
from ..conftest import A, B, C, D, FakeLeaf
from operad import BuildError, Sequential
from ..conftest import A, B, C, FakeLeaf
from pydantic import BaseModel
from operad import Parallel
from ..conftest import A, B, D, FakeLeaf
from typing import Any, Literal
from operad import Agent, BuildError
from operad.agents import Choice, RouteInput, Router, Switch
from tests.conftest import A, B
from operad import Agent, Parallel, Sequential
from operad.core.graph import to_json, to_mermaid
from ..conftest import A, FakeLeaf


# --- from test_composition.py ---
pytestmark = pytest.mark.asyncio


async def test_linear_pipeline_invokes_end_to_end(cfg) -> None:
    class Sequential(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.first = FakeLeaf(
                config=cfg, input=A, output=B, canned={"value": 1}
            )
            self.second = FakeLeaf(
                config=cfg, input=B, output=C, canned={"label": "done"}
            )

        async def forward(self, x: A) -> C:  # type: ignore[override]
            # forward() is called once with sentinel inputs during build()
            # (where intermediates are default-constructed outputs), so it
            # must not branch on payload values - just route.
            mid = (await self.first(x)).response
            return (await self.second(mid)).response

    p = await Sequential().abuild()
    out = await p(A(text="start"))
    assert isinstance(out.response, C)
    assert out.response.label == "done"


async def test_fanout_with_gather_records_all_edges(cfg) -> None:
    class FanOut(Agent):
        input = A
        output = D

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=D)
            self.left = FakeLeaf(
                config=cfg, input=A, output=B, canned={"value": 10}
            )
            self.right = FakeLeaf(
                config=cfg, input=A, output=B, canned={"value": 20}
            )

        async def forward(self, x: A) -> D:  # type: ignore[override]
            a, b = await asyncio.gather(self.left(x), self.right(x))
            return D.model_construct(
                payload=[str(a.response.value), str(b.response.value)]
            )

    f = await FanOut().abuild()
    g = f._graph
    assert len(g.edges) == 2
    callees = {e.callee for e in g.edges}
    assert callees == {"FanOut.left", "FanOut.right"}

    out = await f(A(text="go"))
    assert isinstance(out.response, D)
    assert out.response.payload == ["10", "20"]


async def test_nested_composites_are_captured(cfg) -> None:
    class Inner(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.leaf = FakeLeaf(
                config=cfg, input=A, output=B, canned={"value": 7}
            )

        async def forward(self, x: A) -> B:  # type: ignore[override]
            return (await self.leaf(x)).response

    class Outer(Agent):
        input = A
        output = C

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=C)
            self.inner = Inner()
            self.final = FakeLeaf(
                config=cfg, input=B, output=C, canned={"label": "ok"}
            )

        async def forward(self, x: A) -> C:  # type: ignore[override]
            mid = (await self.inner(x)).response
            return (await self.final(mid)).response

    o = await Outer().abuild()

    # All descendants must be marked built.
    assert o._built is True
    assert o.inner._built is True
    assert o.inner.leaf._built is True
    assert o.final._built is True

    g = o._graph
    callees = {e.callee for e in g.edges}
    assert "Outer.inner" in callees
    assert "Outer.final" in callees
    assert any(e.callee.endswith(".leaf") for e in g.edges)
    by_callee = {e.callee: e for e in g.edges}
    assert by_callee["Outer.inner"].caller == "Outer"
    assert by_callee["Outer.inner.leaf"].caller == "Outer.inner"
    assert by_callee["Outer.final"].caller == "Outer.inner"

    out = await o(A(text="go"))
    assert isinstance(out.response, C)
    assert out.response.label == "ok"


async def test_same_child_called_multiple_times_records_multiple_edges(cfg) -> None:
    class Twice(Agent):
        input = A
        output = B

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=B)
            self.step = FakeLeaf(
                config=cfg, input=A, output=B, canned={"value": 3}
            )

        async def forward(self, x: A) -> B:  # type: ignore[override]
            _ = await self.step(x)
            return (await self.step(x)).response

    t = await Twice().abuild()
    step_edges = [e for e in t._graph.edges if e.callee == "Twice.step"]
    assert len(step_edges) == 2

# --- from test_pipeline.py ---
pytestmark = pytest.mark.asyncio


async def test_pipeline_runs_stages_in_order(cfg) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    second = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "done"})
    p = Sequential(first, second, input=A, output=C)
    await p.abuild()
    out = await p(A(text="hi"))
    assert isinstance(out.response, C)
    assert out.response.label == "done"


async def test_pipeline_captures_every_edge(cfg) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B)
    second = FakeLeaf(config=cfg, input=B, output=C)
    p = Sequential(first, second, input=A, output=C)
    await p.abuild()
    callees = {e.callee for e in p._graph.edges}
    assert callees == {"Sequential.stage_0", "Sequential.stage_1"}


async def test_pipeline_build_rejects_type_mismatch_between_stages(cfg) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B)
    # Second stage expects C but will receive B from stage 0.
    second = FakeLeaf(config=cfg, input=C, output=B)
    p = Sequential(first, second, input=A, output=B)
    with pytest.raises(BuildError) as exc:
        await p.abuild()
    assert exc.value.reason == "input_mismatch"


async def test_pipeline_requires_stages(cfg) -> None:
    with pytest.raises(ValueError, match="at least one stage"):
        Sequential(input=A, output=A)


async def test_pipeline_single_stage_passes_through(cfg) -> None:
    only = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 99})
    p = Sequential(only, input=A, output=B)
    await p.abuild()
    out = await p(A(text="hi"))
    assert isinstance(out.response, B)
    assert out.response.value == 99


async def test_pipeline_composite_needs_no_config(cfg) -> None:
    """Composites are pure routers: their Agent.config is None."""
    only = FakeLeaf(config=cfg, input=A, output=B)
    p = Sequential(only, input=A, output=B)
    assert p.config is None
    await p.abuild()

# --- from test_parallel.py ---
pytestmark = pytest.mark.asyncio


async def test_parallel_fans_out_and_combines(cfg) -> None:
    left = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 10})
    right = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 20})

    def combine(results: dict[str, BaseModel]) -> D:
        return D.model_construct(
            payload=[str(results["left"].value), str(results["right"].value)]
        )

    p = Parallel(
        {"left": left, "right": right},
        input=A,
        output=D,
        combine=combine,
    )
    await p.abuild()
    out = await p(A(text="go"))
    assert out.response.payload == ["10", "20"]


async def test_parallel_records_all_child_edges(cfg) -> None:
    children = {
        "a": FakeLeaf(config=cfg, input=A, output=B),
        "b": FakeLeaf(config=cfg, input=A, output=B),
        "c": FakeLeaf(config=cfg, input=A, output=B),
    }

    def combine(_: dict[str, BaseModel]) -> D:
        return D.model_construct(payload=[])

    p = Parallel(children, input=A, output=D, combine=combine)
    await p.abuild()
    callees = {e.callee for e in p._graph.edges}
    assert callees == {"Parallel.a", "Parallel.b", "Parallel.c"}


async def test_parallel_combine_sees_all_keys(cfg) -> None:
    seen: dict[str, BaseModel] = {}

    def combine(results: dict[str, BaseModel]) -> D:
        seen.update(results)
        return D.model_construct(payload=[])

    children = {
        "x": FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}),
        "y": FakeLeaf(config=cfg, input=A, output=B, canned={"value": 2}),
    }
    p = Parallel(children, input=A, output=D, combine=combine)
    await p.abuild()
    await p(A(text="go"))
    assert set(seen) == {"x", "y"}
    assert seen["x"].value == 1
    assert seen["y"].value == 2


async def test_parallel_requires_children(cfg) -> None:
    with pytest.raises(ValueError, match="at least one child"):
        Parallel(
            {},
            input=A,
            output=D,
            combine=lambda _: D.model_construct(payload=[]),
        )

# --- from test_switch.py ---
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
    assert isinstance(out.response, B)
    assert out.response.value == 1
    assert len(s.branch_a.invocations) == 1  # type: ignore[attr-defined]
    assert s.branch_b.invocations == []  # type: ignore[attr-defined]

    s2 = await _build_switch(label="b").abuild()
    out2 = await s2(A(text="y"))
    assert out2.response.value == 2
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


async def test_switch_build_warns_side_effect_during_trace() -> None:
    from operad.utils.errors import SideEffectDuringTrace

    with pytest.warns(SideEffectDuringTrace) as records:
        await _build_switch(label="a").abuild()
    trace_warnings = [
        r for r in records if issubclass(r.category, SideEffectDuringTrace)
    ]
    assert len(trace_warnings) == 1

# --- from test_deep_nesting.py ---
pytestmark = pytest.mark.asyncio


def _nested_pipeline(depth: int, leaf: Agent) -> Agent:
    current: Agent = leaf
    for _ in range(depth):
        current = Sequential(current, input=A, output=A)
    return current


async def test_ten_level_pipeline_builds_and_exports(cfg) -> None:
    leaf = FakeLeaf(config=cfg, input=A, output=A)
    root = _nested_pipeline(10, leaf)

    await root.abuild()

    mermaid = to_mermaid(root._graph)
    assert mermaid.startswith("flowchart")

    payload = to_json(root._graph)
    assert payload["root"]
    # 10 Sequential composites + 1 leaf = 11 nodes in the captured graph.
    assert len(payload["nodes"]) >= 11
    # Each composite invokes its single stage; 10 edges chain the tree.
    assert len(payload["edges"]) >= 10


async def test_shared_leaf_across_deep_branches_warns_once(cfg) -> None:
    shared = FakeLeaf(config=cfg, input=A, output=A)

    class Branch(Agent):
        input = A
        output = A

        def __init__(self) -> None:
            super().__init__(config=None, input=A, output=A)
            self.leaf = shared

        async def forward(self, x: A) -> A:  # type: ignore[override]
            return (await self.leaf(x)).response

    root = Parallel(
        {"left": Branch(), "right": Branch()},
        input=A,
        output=A,
        combine=lambda r: next(iter(r.values())),
    )

    with pytest.warns(UserWarning, match="shared") as records:
        await root.abuild()
    assert len(records) == 1
