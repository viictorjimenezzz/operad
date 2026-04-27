"""Offline tests for `operad.optim.optimizers.ape.APEOptimizer`."""

from __future__ import annotations

import warnings
from typing import Any

import pytest

from operad.core.agent import _TRACER
from operad.optim.optimizers.ape import (
    APEInput,
    APEOptimizer,
    APEOutput,
    CandidateGenerator,
)
from operad.optim.parameter import TextParameter, TextualGradient
from tests._helpers.fake_leaf import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


class StubCandidateGenerator(CandidateGenerator):
    """Returns a distinct canned candidate per `seed_index`."""

    def __init__(self, *args: Any, canned: list[str] | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._canned = list(canned or [])
        self.calls: list[APEInput] = []

    async def forward(self, x: APEInput) -> APEOutput:  # type: ignore[override]
        if _TRACER.get() is not None:
            return APEOutput(candidate="sentinel")
        self.calls.append(x)
        idx = getattr(x, "seed_index", 0)
        if 0 <= idx < len(self._canned):
            return APEOutput(candidate=self._canned[idx])
        return APEOutput(candidate=f"cand-{idx}")


def _make_role_param(
    cfg: Any, initial: str = "initial"
) -> tuple[FakeLeaf, TextParameter]:
    leaf = FakeLeaf(config=cfg, input=A, output=B)
    leaf.role = initial
    return leaf, TextParameter.from_agent(leaf, "role", "role")


async def _built_gen(cfg: Any, canned: list[str]) -> StubCandidateGenerator:
    return await StubCandidateGenerator(config=cfg, canned=canned).abuild()


async def test_best_of_k_is_adopted(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")
    gen = await _built_gen(cfg, ["cand-a", "cand-b", "cand-c"])
    scores = {"start": 0.1, "cand-a": 0.2, "cand-b": 0.9, "cand-c": 0.5}

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores[candidate]

    opt = APEOptimizer(
        [p],
        evaluator=evaluator,
        generator_factory=lambda: gen,
        k=3,
    )
    await opt.step()

    assert p.value == "cand-b"
    assert len(gen.calls) == 3
    assert sorted(c.seed_index for c in gen.calls) == [0, 1, 2]


async def test_keeps_current_when_no_candidate_improves(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")
    gen = await _built_gen(cfg, ["low-1", "low-2"])
    scores = {"start": 0.9, "low-1": 0.1, "low-2": 0.2}

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores[candidate]

    opt = APEOptimizer(
        [p],
        evaluator=evaluator,
        generator_factory=lambda: gen,
        k=2,
    )
    await opt.step()

    assert p.value == "start"


async def test_grad_ignored_warns_once(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")
    gen = await _built_gen(cfg, ["c-0", "c-1"])
    scores = {"start": 0.1, "c-0": 0.2, "c-1": 0.3}

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return scores[candidate]

    opt = APEOptimizer(
        [p],
        evaluator=evaluator,
        generator_factory=lambda: gen,
        k=2,
    )
    p.grad = TextualGradient(message="tighten", severity=0.8)

    with pytest.warns(UserWarning, match="APEOptimizer ignores"):
        await opt.step()

    # Reset scores for the second step (candidate values reused via fallback).
    scores.update({"c-0": 0.5, "c-1": 0.4})
    p.grad = TextualGradient(message="tighten", severity=0.8)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        await opt.step()
        assert not any(
            issubclass(w.category, UserWarning)
            and "APEOptimizer ignores" in str(w.message)
            for w in caught
        )


async def test_k_zero_rejected(cfg: Any) -> None:
    leaf, p = _make_role_param(cfg, "start")

    async def evaluator(param: TextParameter, candidate: str) -> float:
        return 0.0

    with pytest.raises(ValueError, match="k must be >= 1"):
        APEOptimizer([p], evaluator=evaluator, k=0)
