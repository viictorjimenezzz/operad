"""Tests for `operad.eval.evaluate`."""

from __future__ import annotations

import pytest

from operad import Agent, BuildError, ExactMatch, evaluate

from .conftest import A, B


pytestmark = pytest.mark.asyncio


class _Echo(Agent[A, B]):
    """Deterministic leaf that returns B(value=len(x.text))."""

    input = A
    output = B

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return B.model_construct(value=len(x.text))


async def test_evaluate_reports_per_row_and_summary(cfg) -> None:
    agent = await _Echo(config=cfg).abuild()
    dataset = [
        (A(text="a"), B(value=1)),
        (A(text="bc"), B(value=2)),
        (A(text="xxx"), B(value=3)),
    ]
    report = await evaluate(agent, dataset, [ExactMatch()])
    assert len(report.rows) == 3
    assert report.summary["exact_match"] == 1.0
    for r in report.rows:
        assert r["exact_match"] == 1.0


async def test_evaluate_mixed_scores(cfg) -> None:
    agent = await _Echo(config=cfg).abuild()
    dataset = [
        (A(text="a"), B(value=1)),   # hit
        (A(text="bc"), B(value=99)), # miss
    ]
    report = await evaluate(agent, dataset, [ExactMatch()])
    assert report.summary["exact_match"] == 0.5


async def test_evaluate_rejects_unbuilt_agent(cfg) -> None:
    agent = _Echo(config=cfg)
    with pytest.raises(BuildError) as exc:
        await evaluate(agent, [(A(text="x"), B(value=1))], [ExactMatch()])
    assert exc.value.reason == "not_built"


async def test_evaluate_rejects_bad_concurrency(cfg) -> None:
    agent = await _Echo(config=cfg).abuild()
    with pytest.raises(ValueError, match="concurrency"):
        await evaluate(
            agent, [(A(text="x"), B(value=1))], [ExactMatch()], concurrency=0
        )
