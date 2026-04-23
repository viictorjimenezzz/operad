"""Tests for `operad.Pipeline`: end-to-end wiring + build-time type checks."""

from __future__ import annotations

import pytest

from operad import BuildError, Pipeline

from .conftest import A, B, C, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_pipeline_runs_stages_in_order(cfg) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1})
    second = FakeLeaf(config=cfg, input=B, output=C, canned={"label": "done"})
    p = Pipeline(first, second, input=A, output=C)
    await p.abuild()
    out = await p(A(text="hi"))
    assert isinstance(out.response, C)
    assert out.response.label == "done"


async def test_pipeline_captures_every_edge(cfg) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B)
    second = FakeLeaf(config=cfg, input=B, output=C)
    p = Pipeline(first, second, input=A, output=C)
    await p.abuild()
    callees = {e.callee for e in p._graph.edges}
    assert callees == {"Pipeline.stage_0", "Pipeline.stage_1"}


async def test_pipeline_build_rejects_type_mismatch_between_stages(cfg) -> None:
    first = FakeLeaf(config=cfg, input=A, output=B)
    # Second stage expects C but will receive B from stage 0.
    second = FakeLeaf(config=cfg, input=C, output=B)
    p = Pipeline(first, second, input=A, output=B)
    with pytest.raises(BuildError) as exc:
        await p.abuild()
    assert exc.value.reason == "input_mismatch"


async def test_pipeline_requires_stages(cfg) -> None:
    with pytest.raises(ValueError, match="at least one stage"):
        Pipeline(input=A, output=A)


async def test_pipeline_single_stage_passes_through(cfg) -> None:
    only = FakeLeaf(config=cfg, input=A, output=B, canned={"value": 99})
    p = Pipeline(only, input=A, output=B)
    await p.abuild()
    out = await p(A(text="hi"))
    assert isinstance(out.response, B)
    assert out.response.value == 99


async def test_pipeline_composite_needs_no_config(cfg) -> None:
    """Composites are pure routers: their Agent.config is None."""
    only = FakeLeaf(config=cfg, input=A, output=B)
    p = Pipeline(only, input=A, output=B)
    assert p.config is None
    await p.abuild()
