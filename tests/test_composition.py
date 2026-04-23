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

from .conftest import A, B, C, D, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_linear_pipeline_invokes_end_to_end(cfg) -> None:
    class Pipeline(Agent):
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
            mid = await self.first(x)
            return await self.second(mid)

    p = await Pipeline().abuild()
    out = await p(A(text="start"))
    assert isinstance(out, C)
    assert out.label == "done"


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
                payload=[str(a.value), str(b.value)]
            )

    f = await FanOut().abuild()
    g = f._graph
    assert len(g.edges) == 2
    callees = {e.callee for e in g.edges}
    assert callees == {"FanOut.left", "FanOut.right"}

    out = await f(A(text="go"))
    assert isinstance(out, D)
    assert out.payload == ["10", "20"]


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
            return await self.leaf(x)

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
            mid = await self.inner(x)
            return await self.final(mid)

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

    out = await o(A(text="go"))
    assert isinstance(out, C)
    assert out.label == "ok"


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
            return await self.step(x)

    t = await Twice().abuild()
    step_edges = [e for e in t._graph.edges if e.callee == "Twice.step"]
    assert len(step_edges) == 2
