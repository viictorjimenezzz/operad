"""Tests for `operad.SelfRefine`."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.agents.reasoning.schemas import Reflection, ReflectionInput
from operad.algorithms import SelfRefine
from operad.algorithms.self_refine import RefineInput

from ..conftest import A, B


pytestmark = pytest.mark.asyncio


class _DraftCounter(Agent[A, B]):
    """Leaf that mints `B(value=calls*10)` per call."""

    input = A
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=A, output=B)
        self.calls = 0

    async def forward(self, x) -> B:  # type: ignore[override]
        self.calls += 1
        return B.model_construct(value=self.calls * 10)


class _RefineCounter(Agent[RefineInput, B]):
    """Refiner that mints `B(value=calls*10)` per call."""

    input = RefineInput
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=RefineInput, output=B)
        self.calls = 0

    async def forward(self, x: RefineInput) -> B:  # type: ignore[override]
        self.calls += 1
        return B.model_construct(value=self.calls * 100)


class _AlwaysGoodReflector(Agent[ReflectionInput, Reflection]):
    """Reflector that always says the draft is acceptable."""

    input = ReflectionInput
    output = Reflection

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=ReflectionInput, output=Reflection)

    async def forward(self, x: ReflectionInput) -> Reflection:  # type: ignore[override]
        return Reflection(
            score=0.95,
            needs_revision=False,
            deficiencies=[],
            suggested_revision="",
        )


class _AlwaysBadReflector(Agent[ReflectionInput, Reflection]):
    """Reflector that always demands a revision."""

    input = ReflectionInput
    output = Reflection

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=ReflectionInput, output=Reflection)

    async def forward(self, x: ReflectionInput) -> Reflection:  # type: ignore[override]
        return Reflection(
            score=0.2,
            needs_revision=True,
            deficiencies=["not good enough"],
            suggested_revision="try again",
        )


async def _make_loop(cfg, *, bad_reflector: bool = False, **kwargs) -> SelfRefine:
    loop = SelfRefine(**kwargs)
    loop.generator = await _DraftCounter(cfg).abuild()
    loop.generator.calls = 0
    reflector_cls = _AlwaysBadReflector if bad_reflector else _AlwaysGoodReflector
    loop.reflector = await reflector_cls(cfg).abuild()
    loop.refiner = await _RefineCounter(cfg).abuild()
    loop.refiner.calls = 0
    return loop


async def test_self_refine_converges_on_good_reflection(cfg) -> None:
    loop = await _make_loop(cfg, bad_reflector=False, max_iter=5)
    out = await loop.run(A(text="q"))
    assert out.value == 10
    assert loop.generator.calls == 1


async def test_self_refine_runs_to_max_iter(cfg) -> None:
    loop = await _make_loop(cfg, bad_reflector=True, max_iter=3)
    out = await loop.run(A(text="q"))
    # generator called once for iter 0; refiner called max_iter-1 times
    assert loop.generator.calls == 1
    assert loop.refiner.calls == 2
    assert out.value == 200  # last refiner output: 2 * 100


async def test_self_refine_on_policy_reuses_generator(cfg) -> None:
    loop = SelfRefine(on_policy=True)
    assert loop.refiner is loop.generator


async def test_self_refine_rejects_zero_max_iter() -> None:
    with pytest.raises(ValueError, match="max_iter"):
        SelfRefine(max_iter=0)
