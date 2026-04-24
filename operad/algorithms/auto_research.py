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
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..core.agent import Agent
from ..agents.reasoning.schemas import (
    Answer,
    Hits,
    Query,
    ReflectionInput,
    Task,
)
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
from .judge import Candidate

if TYPE_CHECKING:
    from ..agents.reasoning.components import (
        Critic,
        Planner,
        Reasoner,
        Reflector,
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
    - ``retriever: Agent[Query, Hits]`` (any compatible leaf — e.g.
      ``Retriever``, ``FakeRetriever``, ``BM25Retriever``)
    - ``reasoner: Reasoner[ResearchInput, Answer]``
    - ``critic: Critic`` (``Candidate -> Score``, fixed)
    - ``reflector: Reflector`` (``ReflectionInput -> Reflection``, fixed)

    Each attempt is independent; under concurrency, supply distinct seeds
    via each leaf's ``Configuration.sampling.seed`` to avoid identical
    candidates.

    Example::

        from operad.agents.reasoning.components import FakeRetriever, Hit

        ar = AutoResearcher(
            planner=...,
            retriever=FakeRetriever(
                corpus=[Hit(text="Paris is the capital of France.", score=0.0)]
            ),
            reasoner=...,
            critic=...,
            reflector=...,
        )
    """

    def __init__(
        self,
        *,
        planner: Planner,
        retriever: Agent[Query, Hits],
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
        path = type(self).__name__
        plan = (await self.planner(x)).response
        hits = (await self.retriever(Query(text=plan.query))).response
        draft: Answer = (
            await self.reasoner(ResearchInput(task=x, hits=hits))
        ).response
        score = (
            await self.critic(Candidate(input=x, output=draft))
        ).response.score
        await emit_algorithm_event(
            "iteration",
            algorithm_path=path,
            payload={"iter_index": 0, "phase": "reason", "score": score},
        )
        for iter_index in range(self.max_iter):
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
            await emit_algorithm_event(
                "iteration",
                algorithm_path=path,
                payload={
                    "iter_index": iter_index + 1,
                    "phase": "reflect",
                    "score": score,
                },
            )
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
            await emit_algorithm_event(
                "iteration",
                algorithm_path=path,
                payload={
                    "iter_index": iter_index + 1,
                    "phase": "reason",
                    "score": score,
                },
            )
        return draft, score

    async def run(self, x: Task) -> Answer:
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={
                    "n": self.n,
                    "max_iter": self.max_iter,
                    "threshold": self.threshold,
                },
                started_at=started,
            )
            try:
                pairs = await asyncio.gather(
                    *(self._one_attempt(x) for _ in range(self.n))
                )
                best = max(pairs, key=lambda p: p[1])
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={"score": best[1]},
                    started_at=started,
                    finished_at=time.time(),
                )
                return best[0]
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise


__all__ = ["AutoResearcher", "ResearchInput", "ResearchPlan"]
