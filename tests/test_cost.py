"""Tests for `cost_estimate`: fallback heuristic + custom pricing/tokenizer."""

from __future__ import annotations

import pytest

from operad import OperadOutput, Trace
from operad.runtime.trace import TraceObserver, TraceStep
from operad.runtime.cost import Pricing, cost_estimate
from operad.runtime.observers import base as _obs

from tests.conftest import A, B, FakeLeaf




def _trace_with_tokens(*, prompt: int, completion: int) -> Trace:
    env = OperadOutput[B].model_construct(
        response=B(value=1),
        run_id="r",
        agent_path="X",
        prompt_tokens=prompt,
        completion_tokens=completion,
    )
    return Trace(
        run_id="r",
        steps=[TraceStep(agent_path="X", output=env)],
        root_output={"value": 1},
    )


def test_cost_estimate_sums_tokens_and_defaults_cost_zero() -> None:
    t = _trace_with_tokens(prompt=100, completion=50)
    report = cost_estimate(t)
    assert report.prompt_tokens == 100
    assert report.completion_tokens == 50
    assert report.cost_usd == 0.0  # unknown backend:model → free


def test_cost_estimate_honours_custom_pricing() -> None:
    t = _trace_with_tokens(prompt=1000, completion=500)
    pricing = {"unknown:unknown": Pricing(prompt_per_1k=0.01, completion_per_1k=0.02)}
    report = cost_estimate(t, pricing=pricing)
    assert report.cost_usd == pytest.approx(0.01 + 0.01)


def test_cost_estimate_falls_back_when_tokens_absent() -> None:
    env = OperadOutput[B].model_construct(response=B(value=1), run_id="r", agent_path="X")
    t = Trace(run_id="r", steps=[TraceStep(agent_path="X", output=env)])
    report = cost_estimate(t, tokenizer=lambda s: 42)
    # No prompt text is retained, so tokenizer is invoked with "" → 42.
    assert report.prompt_tokens == 42


@pytest.mark.asyncio
async def test_cost_estimate_on_real_trace(cfg) -> None:
    leaf = await FakeLeaf(config=cfg, input=A, output=B, canned={"value": 1}).abuild()
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await leaf(A(text="x"))
    finally:
        _obs.registry.clear()
    t = obs.last()
    assert t is not None
    report = cost_estimate(t)
    assert report.run_id == t.run_id
    assert len(report.per_step) == len(t.steps)
