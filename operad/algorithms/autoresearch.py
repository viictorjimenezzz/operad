"""Autonomous research loop: plan → retrieve → reason → critique → reflect,
selected best-of-N.

``AutoResearcher`` composes a planner, retriever, reasoner, critic, and
reflector into an opinionated research pipeline. Components are
**class-level defaults** so the typical caller only supplies the
algorithm's own knobs (``context``, ``n``, ``max_iter``, ``threshold``);
to swap in different components, subclass and override the class
attributes.

For each of ``n`` attempts it runs one plan→retrieve→reason cycle,
then iterates reason+reflect while the ``Critic``'s score stays below
``threshold``. Across attempts, the highest final Critic score selects
the winning answer.

Home in ``algorithms/`` because the natural API is ``run(task) -> answer``
over a metric-feedback loop, not ``__call__(x: In) -> Out``.
"""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar

from pydantic import BaseModel, Field

from ..agents.core.pipelines import Loop
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
    Task,
)
from ..core.agent import Agent, _TRACER
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


class ResearchPlan(BaseModel):
    """Typed output of the default planner."""

    query: str = Field(description="Search query to ground the answer.")


class ResearchInput(BaseModel):
    """Typed input the default reasoner receives.

    The ``prior_reflection`` field carries the Reflector's suggested
    revision across inner-loop iterations; it is empty on the first pass.
    """

    task: Task = Field(description="The research task to answer.")
    hits: Hits = Field(description="Retrieved evidence for the task.")
    prior_reflection: str = Field(
        default="",
        description="Revision hint from the prior reflect step.",
    )


class ResearchContext(BaseModel):
    """Durable context shared across every component of an ``AutoResearcher``.

    Rendered into each component's system prompt at construction time
    so the planner, retriever, reasoner, critic, and reflector all
    know the larger problem they are working on. Pass a plain string
    when you just want free-form context; use the structured fields
    when multiple facets matter.
    """

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

    def render(self) -> str:
        parts: list[str] = []
        if self.domain:
            parts.append(f"Domain: {self.domain}")
        if self.audience:
            parts.append(f"Audience: {self.audience}")
        if self.constraints:
            parts.append(f"Constraints: {self.constraints}")
        if self.notes:
            parts.append(f"Notes: {self.notes}")
        return "\n".join(parts)


def _render_context(ctx: "ResearchContext | str") -> str:
    if isinstance(ctx, ResearchContext):
        return ctx.render()
    return ctx


async def _ensure_built(*agents: Agent) -> None:
    pending = [a.abuild() for a in agents if not a._built]
    if pending:
        await asyncio.gather(*pending)


async def _invoke_stage(stage: Agent, x: BaseModel) -> BaseModel:
    if stage._built:
        return (await stage(x)).response
    return await stage.forward(x)


async def _run_loop(loop: Loop, x: BaseModel) -> BaseModel:
    current = x
    for _ in range(loop.n_loops):
        for stage in loop._stages:
            current = await _invoke_stage(stage, current)
    return current


class _AttemptState(BaseModel):
    task: Task | None = None
    hits: Hits = Field(default_factory=Hits)
    draft: Answer | None = None
    score: float = 0.0
    iter_index: int = 0


class _RefineStep(Agent[_AttemptState, _AttemptState]):
    input = _AttemptState
    output = _AttemptState

    def __init__(
        self,
        *,
        reasoner: Agent,
        critic: Agent,
        reflector: Agent,
        threshold: float,
        algorithm_path: str,
    ) -> None:
        super().__init__(config=None, input=_AttemptState, output=_AttemptState)
        self.reasoner = reasoner
        self.critic = critic
        self.reflector = reflector
        self.threshold = threshold
        self.algorithm_path = algorithm_path

    async def forward(self, x: _AttemptState) -> _AttemptState:  # type: ignore[override]
        if x.score >= self.threshold:
            return x

        task = x.task if x.task is not None else Task.model_construct()
        draft = x.draft if x.draft is not None else Answer.model_construct()
        iter_index = x.iter_index + 1
        r = (
            await self.reflector(
                ReflectionInput(
                    original_request=task.goal,
                    candidate_answer=draft.answer,
                )
            )
        ).response
        await emit_algorithm_event(
            "iteration",
            algorithm_path=self.algorithm_path,
            payload={
                "iter_index": iter_index,
                "phase": "reflect",
                "score": x.score,
            },
        )
        draft = (
            await self.reasoner(
                ResearchInput(
                    task=task,
                    hits=x.hits,
                    prior_reflection=r.suggested_revision,
                )
            )
        ).response
        score = (
            await self.critic(Candidate(input=task, output=draft))
        ).response.score
        await emit_algorithm_event(
            "iteration",
            algorithm_path=self.algorithm_path,
            payload={
                "iter_index": iter_index,
                "phase": "reason",
                "score": score,
            },
        )
        return _AttemptState(
            task=task,
            hits=x.hits,
            draft=draft,
            score=score,
            iter_index=iter_index,
        )


class AutoResearcher:
    """Planner → Retriever → Reasoner → Critic → Reflector, best of N.

    The ``Critic`` serves two roles: per-attempt verifier (its score
    gates the reflect inner loop — iteration continues while the score
    is below ``threshold``) and N-selection judge (the attempt with the
    highest final Critic score wins).

    Class-level defaults provide a usable out-of-the-box pipeline.
    Override any of the class attributes in a subclass to swap in a
    differently-configured component.

    Each attempt is independent; under concurrency, distinct seeds on
    the component configs ensure diverse candidates.

    Example::

        ar = AutoResearcher(context="EU energy policy", n=3)
        answer = await ar.run(Task(goal="Summarize the REPowerEU plan."))
    """

    planner: ClassVar[Planner] = Planner(input=Task, output=ResearchPlan)
    retriever: ClassVar[Agent[Query, Hits]] = FakeRetriever(corpus=[])
    reasoner: ClassVar[Reasoner] = Reasoner(input=ResearchInput, output=Answer)
    critic: ClassVar[Critic] = Critic()
    reflector: ClassVar[Reflector] = Reflector()

    def __init__(
        self,
        context: "ResearchContext | str" = "",
        *,
        n: int = 3,
        max_iter: int = 2,
        threshold: float = 0.8,
    ) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if max_iter < 0:
            raise ValueError(f"max_iter must be >= 0, got {max_iter}")

        ctx = _render_context(context)
        cls = type(self)
        self.planner = cls.planner.clone(context=ctx)
        self.retriever = cls.retriever.clone(context=ctx)
        self.reasoner = cls.reasoner.clone(context=ctx)
        self.critic = cls.critic.clone(context=ctx)
        self.reflector = cls.reflector.clone(context=ctx)

        self.context = ctx
        self.n = n
        self.max_iter = max_iter
        self.threshold = threshold

    async def _one_attempt(self, x: Task) -> tuple[Answer, float]:
        path = type(self).__name__
        plan = (await self.planner(x)).response
        hits = (await self.retriever(Query(text=plan.query))).response
        draft = (
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
        if self.max_iter == 0:
            return draft, score

        step = _RefineStep(
            reasoner=self.reasoner,
            critic=self.critic,
            reflector=self.reflector,
            threshold=self.threshold,
            algorithm_path=path,
        )
        loop = Loop(
            step,
            input=_AttemptState,
            output=_AttemptState,
            n_loops=self.max_iter,
        )
        final = await _run_loop(
            loop,
            _AttemptState(
                task=x,
                hits=hits,
                draft=draft,
                score=score,
                iter_index=0,
            ),
        )
        attempt_draft = final.draft if final.draft is not None else Answer.model_construct()
        return attempt_draft, final.score

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
