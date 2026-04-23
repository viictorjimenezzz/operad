"""SelfRefine: generate, reflect, refine until the reflector is satisfied.

Three agents collaborate: a generator (produces the initial answer), a
reflector (reviews and proposes deficiencies + a revision hint), and a
refiner (incorporates the critique into a new answer). The loop stops
once the reflector reports no deficiencies, or after `max_iter` rounds.

NOTE: `ReflectionInput`, `Reflection`, and `RefinementInput` are defined
here as a temporary measure. Stream E ships the canonical Reflector leaf
with its own `ReflectionInput` / `Reflection` types under
`operad.agents.reasoning.components.reflector`. When Stream E merges,
replace these local definitions with imports and delete this module's
copies. See `.conductor/2-F-algorithms.md` "Watch-outs".
"""

from __future__ import annotations

from typing import Any, Generic

from pydantic import BaseModel, Field

from ..core.agent import Agent, In, Out


class ReflectionInput(BaseModel):
    original_request: str = Field(
        default="",
        description="The original request, rendered as a string.",
    )
    candidate_answer: str = Field(
        default="",
        description="The most recent candidate answer, rendered as a string.",
    )


class Reflection(BaseModel):
    needs_revision: bool = Field(
        default=False,
        description="True iff the candidate answer should be revised.",
    )
    deficiencies: list[str] = Field(
        default_factory=list,
        description="Specific problems the reflector identified.",
    )
    suggested_revision: str = Field(
        default="",
        description="A sketch of how to revise the answer (may be empty).",
    )


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
        current: Out = await self.generator(x)
        for _ in range(self.max_iter):
            r = await self.reflector(
                ReflectionInput(
                    original_request=str(x),
                    candidate_answer=str(current),
                )
            )
            if not r.needs_revision:
                return current
            current = await self.refiner(
                RefinementInput(
                    request=str(x),
                    prior=current,
                    critique=r,
                )
            )
        return current
