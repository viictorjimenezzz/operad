"""Runtime error-propagation across composites.

Build-time error paths (`not_built`, `input_mismatch`, `output_mismatch`,
`payload_branch`) are covered by `test_agent.py` and `test_build.py`. This
module pins down what happens after a successful `build()` when a leaf
raises mid-`forward`: `Parallel` surfaces the failure via `asyncio.gather`,
and `Pipeline` halts at the failing stage.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad import Agent, Parallel, Pipeline

from .conftest import A, B, C, D, FakeLeaf


pytestmark = pytest.mark.asyncio


class _RaisingLeaf(Agent[Any, Any]):
    """Leaf whose `forward` raises — declared types still pass build-time tracing."""

    def __init__(
        self,
        *,
        config,
        input: type[BaseModel],
        output: type[BaseModel],
        exc: BaseException | None = None,
    ) -> None:
        super().__init__(config=config, input=input, output=output)
        self._exc = exc if exc is not None else RuntimeError("boom")

    async def forward(self, x: Any) -> Any:
        raise self._exc


class _CountingLeaf(FakeLeaf):
    """FakeLeaf that records each `forward` call on a shared counter."""

    def __init__(self, *, config, input, output, counter: list[int]) -> None:
        super().__init__(config=config, input=input, output=output)
        self._counter = counter

    async def forward(self, x: Any) -> Any:
        self._counter.append(1)
        return await super().forward(x)


async def test_parallel_surfaces_child_exception(cfg) -> None:
    root = Parallel(
        {
            "ok": FakeLeaf(config=cfg, input=A, output=B),
            "bad": _RaisingLeaf(config=cfg, input=A, output=B),
        },
        input=A,
        output=B,
        combine=lambda r: next(iter(r.values())),
    )
    await root.abuild()

    with pytest.raises(RuntimeError, match="boom"):
        await root(A(text="hi"))


async def test_parallel_failure_does_not_call_combine(cfg) -> None:
    combine_calls: list[int] = []

    def combine(r: dict) -> B:
        combine_calls.append(1)
        return next(iter(r.values()))

    root = Parallel(
        {
            "ok": FakeLeaf(config=cfg, input=A, output=B),
            "bad": _RaisingLeaf(config=cfg, input=A, output=B),
        },
        input=A,
        output=B,
        combine=combine,
    )
    await root.abuild()

    # `abuild()` traces combine symbolically once; any runtime invocation
    # would push a second entry. A failing child must short-circuit before
    # combine runs.
    baseline = len(combine_calls)
    with pytest.raises(RuntimeError):
        await root(A(text="hi"))
    assert len(combine_calls) == baseline


async def test_pipeline_stage_raises_halts_downstream(cfg) -> None:
    tripwire: list[int] = []

    root = Pipeline(
        FakeLeaf(config=cfg, input=A, output=B),
        _RaisingLeaf(config=cfg, input=B, output=C),
        _CountingLeaf(config=cfg, input=C, output=D, counter=tripwire),
        input=A,
        output=D,
    )
    await root.abuild()

    with pytest.raises(RuntimeError, match="boom"):
        await root(A(text="hi"))

    assert tripwire == []
