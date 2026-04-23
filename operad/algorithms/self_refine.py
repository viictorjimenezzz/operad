"""SelfRefine: generate, reflect, refine until the reflector is satisfied.

Three agents collaborate: a generator (produces the initial answer), a
reflector (reviews and proposes deficiencies + a revision hint), and a
refiner (incorporates the critique into a new answer). The loop stops
once the reflector reports no deficiencies, or after `max_iter` rounds.

``Reflection`` and ``ReflectionInput`` come from Stream E's Reflector
leaf; ``RefinementInput`` is defined here because it's specific to the
SelfRefine loop.
"""

from __future__ import annotations

from typing import Any, Generic

from pydantic import BaseModel, Field

from ..agents.reasoning.components.reflector import Reflection, ReflectionInput
from ..core.agent import Agent, In, Out


class RefinementInput(BaseModel):
    request: str = Field(
        default="",
        description="The original request, rendered as a string.",
    )
    prior: Any = Field(
        default=None,
        description="The previous answer to be improved.",
    )
    critique: Reflection | None = Field(
        default=None,
        description="The reflector's verdict on the prior answer.",
    )


class SelfRefine(Generic[In, Out]):
    def __init__(
        self,
        generator: Agent[In, Out],
        reflector: Agent[ReflectionInput, Reflection],
        refiner: Agent[RefinementInput, Out],
        *,
        max_iter: int = 2,
    ) -> None:
        if max_iter < 1:
            raise ValueError(f"max_iter must be >= 1, got {max_iter}")
        self.generator = generator
        self.reflector = reflector
        self.refiner = refiner
        self.max_iter = max_iter

    async def run(self, x: In) -> Out:
        current: Out = (await self.generator(x)).response
        for _ in range(self.max_iter):
            r = (
                await self.reflector(
                    ReflectionInput(
                        original_request=str(x),
                        candidate_answer=str(current),
                    )
                )
            ).response
            if not r.needs_revision:
                return current
            current = (
                await self.refiner(
                    RefinementInput(
                        request=str(x),
                        prior=current,
                        critique=r,
                    )
                )
            ).response
        return current
