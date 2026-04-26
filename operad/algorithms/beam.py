"""Beam: sample N candidates, keep the top-K ranked by an optional judge."""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar, Generic

from pydantic import BaseModel, Field

from ..agents.reasoning.components import Critic, Reasoner
from ..agents.reasoning.schemas import Answer, Candidate, Score, Task
from ..core.agent import Agent, In, Out, _TRACER
from ..core.flow import Parallel
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


class CandidateBatch(BaseModel):
    """Outputs from a beam fanout, in candidate-index order."""

    candidates: list[BaseModel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _compose_judge_context(context: str, criteria: str | None) -> str:
    if criteria is None:
        return context
    if context:
        return f"{context}\n\nJudging criteria: {criteria}"
    return f"Judging criteria: {criteria}"


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


# ---------------------------------------------------------------------------
# Algorithm.
# ---------------------------------------------------------------------------


class Beam(Generic[In, Out]):
    """Generate N candidates with ``generator``, return the top ``top_k``."""

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
                generators = {
                    f"candidate_{i}": self.generator.clone()
                    for i in range(self.n)
                }
                if _TRACER.get() is None:
                    await _ensure_built(*generators.values(), self.judge)

                fanout = Parallel(
                    generators,
                    input=self.generator.input,  # type: ignore[arg-type]
                    output=CandidateBatch,
                    combine=lambda results: CandidateBatch(
                        candidates=[
                            results[f"candidate_{i}"] for i in range(self.n)
                        ]
                    ),
                )
                candidates: list[Out] = (
                    await fanout.forward(x)
                ).candidates  # type: ignore[assignment]

                if self.judge is None:
                    scores: list[Score | None] = [None] * self.n
                    order = list(range(self.n))
                    phase = "truncate"
                else:
                    judge_outputs = await asyncio.gather(
                        *(
                            self.judge(Candidate(input=x, output=candidates[i]))
                            for i in range(self.n)
                        )
                    )
                    scores = [j.response for j in judge_outputs]
                    order = sorted(
                        range(self.n),
                        key=lambda i: -scores[i].score,  # type: ignore[union-attr]
                    )
                    phase = "prune"

                for i, candidate in enumerate(candidates):
                    score = scores[i].score if scores[i] is not None else None
                    await emit_algorithm_event(
                        "candidate",
                        algorithm_path=path,
                        payload={
                            "iter_index": 0,
                            "candidate_index": i,
                            "score": score,
                            "text": _as_text(candidate),
                        },
                    )

                top = order[: self.top_k]
                dropped = [i for i in order if i not in top]
                top_scores = [
                    scores[i].score if scores[i] is not None else None
                    for i in top
                ]
                await emit_algorithm_event(
                    "iteration",
                    algorithm_path=path,
                    payload={
                        "iter_index": 0,
                        "phase": phase,
                        "score": max((s.score for s in scores if s is not None), default=None),
                        "top_indices": top,
                        "dropped_indices": dropped,
                    },
                )
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={"top_indices": top, "top_scores": top_scores},
                    started_at=started,
                    finished_at=time.time(),
                )

                if self.judge is None:
                    return [candidates[i] for i in top]

                scored_candidates = [
                    self._inject_score(candidates[i], scores[i].score)  # type: ignore[union-attr]
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
