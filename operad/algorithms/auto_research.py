"""Autonomous research loop: plan → retrieve → reason → critique → reflect,
selected best-of-N.

``AutoResearcher`` composes existing reasoning leaves into an opinionated
research pipeline. For each of ``n`` attempts it runs one
plan→retrieve→reason cycle, then iterates reason+reflect while the
``Critic``'s score stays below ``threshold``. Across attempts, the
highest final Critic score selects the winning answer.

Home in ``algorithms/`` because the natural API is ``run(task) -> answer``
over a metric-feedback loop, not ``__call__(x: In) -> Out``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..agents.reasoning.schemas import (
    Answer,
    Hits,
    Query,
    ReflectionInput,
    Task,
)
from .judge import Candidate

if TYPE_CHECKING:
    from ..agents.reasoning.components import (
        Critic,
        Planner,
        Reasoner,
        Reflector,
        Retriever,
    )


class ResearchPlan(BaseModel):
    """Typed output of the caller's Planner.

    Pin your planner as ``Planner[Task, ResearchPlan]`` — its ``query``
    field is fed directly to the Retriever.
    """

    query: str = Field(description="Search query to ground the answer.")


class ResearchInput(BaseModel):
    """Typed input the caller's Reasoner receives.

    Pin your reasoner as ``Reasoner[ResearchInput, Answer]``. The
    ``prior_reflection`` field carries the Reflector's suggested revision
    across inner-loop iterations; it is empty on the first pass.
    """

    task: Task = Field(description="The research task to answer.")
    hits: Hits = Field(description="Retrieved evidence for the task.")
    prior_reflection: str = Field(
        default="",
        description="Revision hint from the prior reflect step.",
    )


class AutoResearcher:
    """Planner → Retriever → Reasoner → Critic → Reflector, best of N.

    The ``Critic`` serves two roles: per-attempt verifier (its score
    gates the reflect inner loop — iteration continues while the score is
    below ``threshold``) and N-selection judge (the attempt with the
    highest final Critic score wins).

    Callers pin the leaves' generic types:

    - ``planner: Planner[Task, ResearchPlan]``
    - ``retriever: Retriever`` (``Query -> Hits``, fixed)
    - ``reasoner: Reasoner[ResearchInput, Answer]``
    - ``critic: Critic`` (``Candidate -> Score``, fixed)
    - ``reflector: Reflector`` (``ReflectionInput -> Reflection``, fixed)

    Each attempt is independent; under concurrency, supply distinct seeds
    via each leaf's ``Configuration.sampling.seed`` to avoid identical
    candidates.
    """

    def __init__(
        self,
        *,
        planner: Planner,
        retriever: Retriever,
        reasoner: Reasoner,
        critic: Critic,
        reflector: Reflector,
        n: int = 3,
        max_iter: int = 2,
        threshold: float = 0.8,
    ) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if max_iter < 0:
            raise ValueError(f"max_iter must be >= 0, got {max_iter}")
        self.planner = planner
        self.retriever = retriever
        self.reasoner = reasoner
        self.critic = critic
        self.reflector = reflector
        self.n = n
        self.max_iter = max_iter
        self.threshold = threshold

    async def _one_attempt(self, x: Task) -> tuple[Answer, float]:
        plan = (await self.planner(x)).response
        hits = (await self.retriever(Query(text=plan.query))).response
        draft: Answer = (
            await self.reasoner(ResearchInput(task=x, hits=hits))
        ).response
        score = (
            await self.critic(Candidate(input=x, output=draft))
        ).response.score
        for _ in range(self.max_iter):
            if score >= self.threshold:
                break
            r = (
                await self.reflector(
                    ReflectionInput(
                        original_request=x.goal,
                        candidate_answer=draft.answer,
                    )
                )
            ).response
            draft = (
                await self.reasoner(
                    ResearchInput(
                        task=x,
                        hits=hits,
                        prior_reflection=r.suggested_revision,
                    )
                )
            ).response
            score = (
                await self.critic(Candidate(input=x, output=draft))
            ).response.score
        return draft, score

    async def run(self, x: Task) -> Answer:
        pairs = await asyncio.gather(
            *(self._one_attempt(x) for _ in range(self.n))
        )
        return max(pairs, key=lambda p: p[1])[0]


__all__ = ["AutoResearcher", "ResearchInput", "ResearchPlan"]
