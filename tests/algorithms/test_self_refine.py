"""Tests for `operad.SelfRefine`."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.agents import Reflection, ReflectionInput
from operad.algorithms import RefinementInput, SelfRefine

from ..conftest import A, B


pytestmark = pytest.mark.asyncio


class _Gen(Agent[A, B]):
    input = A
    output = B

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return B.model_construct(value=1)


class _Reflector(Agent[ReflectionInput, Reflection]):
    input = ReflectionInput
    output = Reflection

    def __init__(self, cfg, scripted: list[bool]) -> None:
        super().__init__(config=cfg, input=ReflectionInput, output=Reflection)
        self.scripted = list(scripted)
        self.calls = 0

    async def forward(self, x: ReflectionInput) -> Reflection:  # type: ignore[override]
        i = min(self.calls, len(self.scripted) - 1)
        needs = self.scripted[i]
        self.calls += 1
        return Reflection(
            needs_revision=needs,
            deficiencies=["d"] if needs else [],
            suggested_revision="s" if needs else "",
        )


class _Refiner(Agent[RefinementInput, B]):
    input = RefinementInput
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=RefinementInput, output=B)
        self.calls = 0

    async def forward(self, x: RefinementInput) -> B:  # type: ignore[override]
        self.calls += 1
        prior_val = getattr(x.prior, "value", 0)
        return B.model_construct(value=prior_val + 1)


async def test_self_refine_terminates_when_reflector_satisfied(cfg) -> None:
    gen = await _Gen(config=cfg).abuild()
    reflector = await _Reflector(cfg, scripted=[False]).abuild()
    refiner = await _Refiner(cfg).abuild()
    reflector.calls = 0
    refiner.calls = 0

    loop = SelfRefine(gen, reflector, refiner, max_iter=3)
    out = await loop.run(A(text="q"))
    assert out.value == 1
    assert reflector.calls == 1
    assert refiner.calls == 0


async def test_self_refine_iterates_and_refines(cfg) -> None:
    gen = await _Gen(config=cfg).abuild()
    reflector = await _Reflector(cfg, scripted=[True, True, False]).abuild()
    refiner = await _Refiner(cfg).abuild()
    reflector.calls = 0
    refiner.calls = 0

    loop = SelfRefine(gen, reflector, refiner, max_iter=5)
    out = await loop.run(A(text="q"))
    assert refiner.calls == 2
    assert out.value == 3  # initial=1, +1 twice


async def test_self_refine_returns_after_max_iter(cfg) -> None:
    gen = await _Gen(config=cfg).abuild()
    reflector = await _Reflector(cfg, scripted=[True]).abuild()
    refiner = await _Refiner(cfg).abuild()
    reflector.calls = 0
    refiner.calls = 0

    loop = SelfRefine(gen, reflector, refiner, max_iter=2)
    out = await loop.run(A(text="q"))
    assert refiner.calls == 2
    assert out.value == 3


async def test_self_refine_rejects_zero_max_iter(cfg) -> None:
    gen = _Gen(config=cfg)
    reflector = _Reflector(cfg, scripted=[False])
    refiner = _Refiner(cfg)
    with pytest.raises(ValueError, match="max_iter"):
        SelfRefine(gen, reflector, refiner, max_iter=0)
