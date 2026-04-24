"""Offline tests for `operad.data.UncertaintySampler`."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from operad.agents.reasoning.schemas import Candidate, Score
from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.data import DataLoader, UncertaintySampler
from tests._helpers.fake_leaf import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


def _dataset(n: int = 6) -> Dataset[A, B]:
    entries = [Entry(input=A(text=f"x{i}"), expected_output=B(value=i)) for i in range(n)]
    return Dataset(entries, name="u", version="v1")


class _IndexAwareLeaf(FakeLeaf):
    """Returns `B(value=i)` mirroring the input's text suffix."""

    async def forward(self, x: Any) -> Any:
        try:
            i = int(str(getattr(x, "text", "x0"))[1:])
        except ValueError:
            i = 0
        return self.output.model_construct(value=i)


class _IndexAwareScorer(FakeLeaf):
    """Scores 0.5 (peak uncertainty) on even indices, 0.9 on odd."""

    async def forward(self, x: Candidate[Any, Any]) -> Any:
        v = getattr(x.output, "value", 0) if x.output is not None else 0
        score_val = 0.5 if v % 2 == 0 else 0.9
        return self.output.model_construct(score=score_val, rationale="")


async def _built_agent(cfg: Any) -> _IndexAwareLeaf:
    leaf = _IndexAwareLeaf(config=cfg, input=A, output=B, canned={})
    await leaf.abuild()
    return leaf


async def _built_scorer(cfg: Any) -> _IndexAwareScorer:
    scorer = _IndexAwareScorer(config=cfg, input=Candidate, output=Score, canned={})
    await scorer.abuild()
    return scorer


async def test_refresh_required_before_iter(cfg: Any) -> None:
    ds = _dataset(4)
    agent = await _built_agent(cfg)
    sampler = UncertaintySampler(ds, agent)
    with pytest.raises(RuntimeError, match="refresh"):
        iter(sampler)


async def test_weights_favor_uncertain_examples(cfg: Any) -> None:
    ds = _dataset(6)
    agent = await _built_agent(cfg)
    scorer = await _built_scorer(cfg)
    sampler = UncertaintySampler(
        ds, agent, scorer=scorer, num_samples=300, seed=7
    )
    await sampler.refresh()
    picks = list(iter(sampler))
    even = sum(1 for p in picks if p % 2 == 0)
    odd = sum(1 for p in picks if p % 2 == 1)
    assert even > odd


async def test_deterministic_with_seed(cfg: Any) -> None:
    ds = _dataset(6)
    agent = await _built_agent(cfg)
    scorer = await _built_scorer(cfg)

    a = UncertaintySampler(ds, agent, scorer=scorer, num_samples=50, seed=7)
    await a.refresh()
    b = UncertaintySampler(ds, agent, scorer=scorer, num_samples=50, seed=7)
    await b.refresh()
    assert list(iter(a)) == list(iter(b))


async def test_num_samples_controls_len(cfg: Any) -> None:
    ds = _dataset(10)
    agent = await _built_agent(cfg)
    scorer = await _built_scorer(cfg)
    sampler = UncertaintySampler(
        ds, agent, scorer=scorer, num_samples=3, seed=1
    )
    await sampler.refresh()
    assert len(sampler) == 3
    picks = list(iter(sampler))
    assert len(picks) == 3


async def test_refresh_every_elides_work(cfg: Any) -> None:
    ds = _dataset(4)
    agent = await _built_agent(cfg)
    scorer = await _built_scorer(cfg)

    calls = {"agent": 0}
    original_forward = agent.forward.__func__  # type: ignore[attr-defined]

    async def _counting_forward(self: Any, x: Any) -> Any:
        calls["agent"] += 1
        return await original_forward(self, x)

    agent.forward = _counting_forward.__get__(agent, type(agent))  # type: ignore[attr-defined]

    sampler = UncertaintySampler(
        ds, agent, scorer=scorer, num_samples=2, seed=1, refresh_every=2
    )
    await sampler.refresh()  # epoch 0 → work
    first = calls["agent"]
    await sampler.refresh()  # epoch 1 → elide
    second = calls["agent"]
    await sampler.refresh()  # epoch 2 → work
    third = calls["agent"]
    assert first == len(ds)
    assert second == first  # no new work
    assert third == first + len(ds)


async def test_trainer_invokes_sampler_refresh(cfg: Any) -> None:
    """Smoke: Trainer.fit with an UncertaintySampler-backed loader completes."""
    from operad.optim.optimizer import Optimizer, ParamGroup
    from operad.optim.parameter import Parameter, TextualGradient
    from operad.metrics.base import MetricBase
    from operad.train import Trainer

    class _StubLoss(MetricBase):
        name: str = "stub_loss"

        async def score(
            self, predicted: BaseModel, expected: BaseModel
        ) -> float:
            return 0.5

        async def compute(
            self, predicted: BaseModel, expected: BaseModel | None
        ) -> tuple[float, TextualGradient]:
            return 0.5, TextualGradient.null_gradient()

    class _NoopOptimizer(Optimizer):
        def __init__(self, params: Any) -> None:
            super().__init__(params, defaults={"lr": 1.0})

        async def step(self) -> None:
            return None

        async def _apply_param_update(
            self, param: Parameter[Any], group: ParamGroup
        ) -> None:
            return None

    ds = _dataset(4)
    agent = await _built_agent(cfg)
    agent.mark_trainable(role=True)
    scorer = await _built_scorer(cfg)
    sampler = UncertaintySampler(
        ds, agent, scorer=scorer, num_samples=4, seed=1
    )
    loader = DataLoader(ds, batch_size=2, sampler=sampler)
    trainer = Trainer(agent, _NoopOptimizer(list(agent.parameters())), _StubLoss())
    await trainer.fit(loader, epochs=1)
    assert sampler._weights is not None
