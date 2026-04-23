"""Tests for `operad.Parallel`: fan-out + combine."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad import Parallel

from .conftest import A, B, D, FakeLeaf


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
    assert out.payload == ["10", "20"]


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
