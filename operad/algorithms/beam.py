"""Beam: sample N candidates, keep the top-K ranked by an optional judge.

``Beam`` is an algorithm, not an Agent. It orchestrates a generator
and a judge (both of which *are* Agents) to close a metric-driven
loop. Components are **class-level defaults** so callers typically
supply only the algorithm's own knobs (``context``, ``criteria``,
``n``, ``top_k``); swap components via a subclass.

Defaults use a generic ``Reasoner[Task, Answer]`` as the generator and
``Critic`` as the judge. Set ``judge=None`` for "keep generation order"
behaviour (no ranking). To embed a ``Beam`` inside a composite Agent,
wrap it in a small leaf that calls ``await beam.run(x)`` from its own
``forward``.
"""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar, Generic

from pydantic import BaseModel, Field

from ..agents.pipelines import Parallel
from ..agents.reasoning.components import Critic, Reasoner
from ..agents.reasoning.schemas import Answer, Candidate, Score, Task
from ..core.agent import Agent, In, Out, _TRACER
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


def _compose_judge_context(context: str, criteria: str | None) -> str:
    if criteria:
        if context:
            return f"{context}\n\nJudging criteria: {criteria}"
        return f"Judging criteria: {criteria}"
    return context


def _as_text(x: object) -> str:
    if x is None:
        return ""
    answer = getattr(x, "answer", None)
    if isinstance(answer, str):
        return answer
    return str(x)


async def _ensure_built(*agents: Agent | None) -> None:
    pending = [a.abuild() for a in agents if a is not None and not a._built]
    if pending:
        await asyncio.gather(*pending)


class _CandidateBatch(BaseModel):
    candidates: list[BaseModel] = Field(default_factory=list)


class Beam(Generic[In, Out]):
    """Generate N candidates with ``generator``, return the top ``top_k``
    by ``judge`` score.

    ``judge`` (when present) is an ``Agent[Candidate[In, Out], Score]``
    that sees both the original request and a candidate and returns a
    ``Score``.
    When ``top_k == 1`` the return value is still a one-element list
    so callers have a single shape to consume.
    """

    generator: ClassVar[Agent] = Reasoner(input=Task, output=Answer)
    judge: ClassVar[Agent | None] = Critic()

    def __init__(
        self,
        context: str = "",
        *,
        criteria: str | None = None,
        n: int = 4,
        top_k: int | None = None,
    ) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        if top_k is None:
            top_k = n
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if top_k > n:
            raise ValueError(f"top_k ({top_k}) must be <= n ({n})")

        cls = type(self)
        self.generator = cls.generator.clone(context=context)
        self.judge = None
        if cls.judge is not None:
            self.judge = cls.judge.clone(
                context=_compose_judge_context(context, criteria)
            )

        self.context = context
        self.criteria = criteria
        self.n = n
        self.top_k = top_k

    @staticmethod
    def _inject_score(candidate: Out, score: float) -> Out:
        if not isinstance(candidate, BaseModel):
            return candidate
        if "score" not in candidate.__class__.model_fields:
            return candidate
        return candidate.model_copy(update={"score": score})  # type: ignore[return-value]

    async def run(self, x: In) -> list[Out]:
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={"n": self.n, "top_k": self.top_k},
                started_at=started,
            )
            try:
                if _TRACER.get() is None:
                    await _ensure_built(self.generator, self.judge)

                generator_fanout = Parallel(
                    {f"candidate_{i}": self.generator for i in range(self.n)},
                    input=self.generator.input,  # type: ignore[arg-type]
                    output=_CandidateBatch,
                    combine=lambda results: _CandidateBatch(
                        candidates=[
                            results[f"candidate_{i}"] for i in range(self.n)
                        ]
                    ),
                )
                candidate_batch = await generator_fanout.forward(x)
                candidates: list[Out] = candidate_batch.candidates  # type: ignore[assignment]
                if self.judge is None:
                    for i in range(self.n):
                        await emit_algorithm_event(
                            "candidate",
                            algorithm_path=path,
                            payload={
                                "iter_index": 0,
                                "candidate_index": i,
                                "score": None,
                                "text": _as_text(candidates[i]),
                            },
                        )
                    top = list(range(self.n))[: self.top_k]
                    dropped = [i for i in range(self.n) if i not in top]
                    await emit_algorithm_event(
                        "iteration",
                        algorithm_path=path,
                        payload={
                            "iter_index": 0,
                            "phase": "truncate",
                            "score": None,
                            "top_indices": top,
                            "dropped_indices": dropped,
                        },
                    )
                    await emit_algorithm_event(
                        "algo_end",
                        algorithm_path=path,
                        payload={
                            "top_indices": top,
                            "top_scores": [None for _ in top],
                        },
                        started_at=started,
                        finished_at=time.time(),
                    )
                    return [candidates[i] for i in top]
                assert self.judge is not None
                judge_outputs = await asyncio.gather(
                    *(
                        self.judge(Candidate(input=x, output=candidates[i]))
                        for i in range(self.n)
                    )
                )
                scores: list[Score] = [j.response for j in judge_outputs]
                for i, s in enumerate(scores):
                    await emit_algorithm_event(
                        "candidate",
                        algorithm_path=path,
                        payload={
                            "iter_index": 0,
                            "candidate_index": i,
                            "score": s.score,
                            "text": _as_text(candidates[i]),
                        },
                    )
                order = sorted(range(self.n), key=lambda i: -scores[i].score)
                top = order[: self.top_k]
                dropped = [i for i in order if i not in top]
                await emit_algorithm_event(
                    "iteration",
                    algorithm_path=path,
                    payload={
                        "iter_index": 0,
                        "phase": "prune",
                        "score": max((s.score for s in scores), default=None),
                        "top_indices": top,
                        "dropped_indices": dropped,
                    },
                )
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "top_indices": top,
                        "top_scores": [scores[i].score for i in top],
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                scored_candidates: list[Out] = [
                    self._inject_score(candidates[i], scores[i].score)
                    for i in range(self.n)
                ]
                return [scored_candidates[i] for i in top]
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise


__all__ = ["Beam"]
