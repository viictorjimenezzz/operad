"""Focused tests for `Loop` and custom root naming on compositional agents."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.agents import Loop

from ..conftest import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


class _Append(Agent[A, A]):
    input = A
    output = A

    def __init__(self, suffix: str) -> None:
        super().__init__(config=None, input=A, output=A)
        self._suffix = suffix

    async def forward(self, x: A) -> A:  # type: ignore[override]
        return A(text=x.text + self._suffix)


async def test_loop_runs_full_sequence_n_times() -> None:
    loop = Loop(
        _Append("a"),
        _Append("b"),
        input=A,
        output=A,
        n_loops=3,
    )
    await loop.abuild()
    out = await loop(A(text="x"))
    assert out.response.text == "xababab"


async def test_loop_requires_same_input_output_type(cfg) -> None:
    with pytest.raises(ValueError, match="input.*output.*same type"):
        Loop(
            FakeLeaf(config=cfg, input=A, output=B),
            input=A,
            output=B,  # type: ignore[arg-type]
            n_loops=1,
        )


async def test_loop_requires_positive_n_loops() -> None:
    with pytest.raises(ValueError, match="n_loops >= 1"):
        Loop(_Append("!"), input=A, output=A, n_loops=0)


async def test_loop_custom_name_sets_graph_and_runtime_root() -> None:
    loop = Loop(
        _Append("!"),
        input=A,
        output=A,
        n_loops=2,
        name="rewrite_loop",
    )
    await loop.abuild()
    assert loop._graph.root == "rewrite_loop"
    assert loop.graph_json()["root"] == "rewrite_loop"
    assert {(e.caller, e.callee) for e in loop._graph.edges} == {
        ("rewrite_loop", "rewrite_loop.stage_0"),
        ("rewrite_loop.stage_0", "rewrite_loop.stage_0"),
    }

    out = await loop(A(text="go"))
    assert out.response.text == "go!!"
    assert out.agent_path == "rewrite_loop"


async def test_loop_mermaid_shows_cycle_even_single_pass() -> None:
    loop = Loop(
        _Append("!"),
        input=A,
        output=A,
        n_loops=1,
    )
    await loop.abuild()
    text = loop.graph_mermaid()
    assert "Loop_stage_0 -->|\"A -> A\"| Loop_stage_0" in text
