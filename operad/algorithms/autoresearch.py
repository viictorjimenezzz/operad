"""Autonomous research: plan -> retrieve -> reason -> critique -> reflect.

``AutoResearcher`` composes a planner, retriever, reasoner, critic, and
reflector into an opinionated research pipeline. Components are
class-level defaults, so typical callers provide a ``ResearchContext`` to
``run`` and only tune the algorithm knobs at construction time.
"""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar

from pydantic import BaseModel, Field

from ..agents.reasoning.components import (
    Critic,
    FakeRetriever,
    Planner,
    Reasoner,
    Reflector,
)
from ..agents.reasoning.schemas import (
    Answer,
    Candidate,
    Hits,
    Query,
    ReflectionInput,
)
from ..core.agent import Agent, _TRACER
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


class ResearchContext(BaseModel):
    """The research request and durable context for every component."""

    goal: str = Field(description="The research question or objective to answer.")
    domain: str = Field(
        default="",
        description="Subject-matter area, e.g. 'climate science' or 'legal research'.",
    )
    audience: str = Field(
        default="",
        description="Who the final answer is for; shapes register and depth.",
    )
    constraints: str = Field(
        default="",
        description="Hard constraints: citation style, length, forbidden sources.",
    )
    notes: str = Field(
        default="",
        description="Any additional free-form context worth propagating.",
    )


class ResearchPlan(BaseModel):
    """Typed output of the planner."""

    query: str = Field(description="Search query to ground the answer.")


class ResearchInput(BaseModel):
    """Typed input the reasoner receives after retrieval."""

    context: ResearchContext = Field(description="The original research request.")
    hits: Hits = Field(description="Retrieved evidence for the request.")
    prior_reflection: str = Field(
        default="",
        description="Revision hint from the prior reflect step.",
    )


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _ensure_built(*agents: Agent) -> None:
    pending = [a.abuild() for a in agents if not a._built]
    if pending:
        await asyncio.gather(*pending)


# ---------------------------------------------------------------------------
# Algorithm.
# ---------------------------------------------------------------------------


class AutoResearcher:
    """Planner -> retriever -> reasoner, with critique/reflection refinement.

    Each attempt is independent. ``n`` controls best-of-N sampling,
    ``threshold`` controls early acceptance, and ``max_iter`` caps
    reflection/refinement passes after the first draft.
    """

    planner: ClassVar[Planner] = Planner(input=ResearchContext, output=ResearchPlan)
    retriever: ClassVar[Agent[Query, Hits]] = FakeRetriever(corpus=[])
    reasoner: ClassVar[Reasoner] = Reasoner(input=ResearchInput, output=Answer)
    critic: ClassVar[Critic] = Critic()
    reflector: ClassVar[Reflector] = Reflector()

    def __init__(
        self,
        *,
        n: int = 3,
        max_iter: int = 2,
        threshold: float = 0.8,
    ) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if max_iter < 0:
            raise ValueError(f"max_iter must be >= 0, got {max_iter}")

        cls = type(self)
        self.planner = cls.planner.clone()
        self.retriever = cls.retriever.clone()
        self.reasoner = cls.reasoner.clone()
        self.critic = cls.critic.clone()
        self.reflector = cls.reflector.clone()

        self.n = n
        self.max_iter = max_iter
        self.threshold = threshold

    async def _one_attempt(self, x: ResearchContext) -> tuple[Answer, float]:
        path = type(self).__name__
        plan = (await self.planner(x)).response
        hits = (await self.retriever(Query(text=plan.query))).response
        draft = (
            await self.reasoner(ResearchInput(context=x, hits=hits))
        ).response
        score = (
            await self.critic(Candidate(input=x, output=draft))
        ).response.score
        await emit_algorithm_event(
            "iteration",
            algorithm_path=path,
            payload={"iter_index": 0, "phase": "reason", "score": score},
        )

        for iter_index in range(1, self.max_iter + 1):
            if score >= self.threshold:
                break

            reflection = (
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
                    "iter_index": iter_index,
                    "phase": "reflect",
                    "score": score,
                },
            )
            draft = (
                await self.reasoner(
                    ResearchInput(
                        context=x,
                        hits=hits,
                        prior_reflection=reflection.suggested_revision,
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
                    "iter_index": iter_index,
                    "phase": "reason",
                    "score": score,
                },
            )
        return draft, score

    async def run(self, x: ResearchContext) -> Answer:
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
                if _TRACER.get() is None:
                    await _ensure_built(
                        self.planner,
                        self.retriever,
                        self.reasoner,
                        self.critic,
                        self.reflector,
                    )
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


__all__ = [
    "AutoResearcher",
    "ResearchContext",
    "ResearchInput",
    "ResearchPlan",
]
