"""Tests for the `evaluate` dataset harness."""

from __future__ import annotations

import asyncio

import pytest

from operad import BuildError, EvalReport, ExactMatch, evaluate

from .conftest import A, FakeLeaf


pytestmark = pytest.mark.asyncio


async def test_evaluate_happy_path(cfg) -> None:
    agent = FakeLeaf(
        config=cfg, input=A, output=A, canned={"text": "hello"},
    )
    await agent.abuild()

    dataset = [
        (A(text="q1"), A(text="hello")),   # match
        (A(text="q2"), A(text="hello")),   # match
        (A(text="q3"), A(text="other")),   # mismatch
    ]
    report = await evaluate(agent, dataset, [ExactMatch()])

    assert isinstance(report, EvalReport)
    assert len(report.rows) == 3
    assert report.summary["exact_match"] == pytest.approx(2 / 3)
    assert report.rows[0]["input"] == {"text": "q1"}
    assert report.rows[0]["predicted"] == {"text": "hello"}
    assert report.rows[0]["exact_match"] == 1.0
    assert report.rows[2]["exact_match"] == 0.0


async def test_evaluate_raises_when_not_built(cfg) -> None:
    agent = FakeLeaf(config=cfg, input=A, output=A, canned={"text": "x"})
    with pytest.raises(BuildError) as exc:
        await evaluate(agent, [(A(), A())], [ExactMatch()])
    assert exc.value.reason == "not_built"


async def test_evaluate_respects_concurrency_bound(cfg) -> None:
    inflight = 0
    max_inflight = 0

    class SlowLeaf(FakeLeaf):
        async def forward(self, x):  # type: ignore[override]
            nonlocal inflight, max_inflight
            inflight += 1
            max_inflight = max(max_inflight, inflight)
            await asyncio.sleep(0.02)
            inflight -= 1
            return self.output.model_construct(**self.canned)

    agent = SlowLeaf(config=cfg, input=A, output=A, canned={"text": "hi"})
    await agent.abuild()

    dataset = [(A(text=str(i)), A(text="hi")) for i in range(8)]
    await evaluate(agent, dataset, [ExactMatch()], concurrency=2)
    assert max_inflight <= 2
    assert max_inflight >= 1
