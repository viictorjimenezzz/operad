"""VerifierLoop: regenerate until a critic is satisfied.

The generator is called up to ``max_iter`` times; each candidate is
scored by the critic (an ``Agent[Candidate[In, Out], Score]``). The
loop exits early the first time a score clears ``threshold``,
otherwise it returns the last candidate. Randomisation, if any, lives
on the generator's sampling config — not here.

Components are **class-level defaults** so callers typically supply
only the algorithm's own knobs (``context``, ``threshold``,
``max_iter``); swap components via a subclass.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, ClassVar, Generic

from pydantic import BaseModel, Field

from ..agents.core.pipelines import Loop
from ..agents.reasoning.components import Critic, Reasoner
from ..agents.reasoning.schemas import Answer, Candidate, Score, Task
from ..core.agent import Agent, In, Out, _TRACER
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


def _as_text(x: object) -> str:
    if x is None:
        return ""
    answer = getattr(x, "answer", None)
    if isinstance(answer, str):
        return answer
    return str(x)


async def _ensure_built(*agents: Agent[Any, Any]) -> None:
    pending = [a.abuild() for a in agents if not a._built]
    if pending:
        await asyncio.gather(*pending)


async def _invoke_stage(stage: Agent[Any, Any], x: BaseModel) -> BaseModel:
    if stage._built:
        return (await stage(x)).response
    return await stage.forward(x)


async def _run_loop(loop: Loop[Any], x: BaseModel) -> BaseModel:
    current = x
    for _ in range(loop.n_loops):
        for stage in loop._stages:
            current = await _invoke_stage(stage, current)
    return current


class _VerifierState(BaseModel):
    request: BaseModel | None = None
    candidate: BaseModel | None = None
    score: float | None = None
    iterations: int = 0
    converged: bool = False


class _VerifyStep(Agent[_VerifierState, _VerifierState]):
    input = _VerifierState
    output = _VerifierState

    def __init__(
        self,
        *,
        generator: Agent[Any, Any],
        critic: Agent[Any, Any],
        threshold: float,
        algorithm_path: str,
    ) -> None:
        super().__init__(config=None, input=_VerifierState, output=_VerifierState)
        self.generator = generator
        self.critic = critic
        self.threshold = threshold
        self.algorithm_path = algorithm_path

    async def forward(self, x: _VerifierState) -> _VerifierState:  # type: ignore[override]
        if x.converged:
            return x

        request = x.request
        if request is None:
            request = self.generator.input.model_construct()

        candidate = (await self.generator(request)).response
        score = (await self.critic(Candidate(input=request, output=candidate))).response
        iter_index = x.iterations

        await emit_algorithm_event(
            "iteration",
            algorithm_path=self.algorithm_path,
            payload={
                "iter_index": iter_index,
                "phase": "verify",
                "score": score.score,
                "text": _as_text(candidate),
            },
        )

        return _VerifierState(
            request=request,
            candidate=candidate,
            score=score.score,
            iterations=x.iterations + 1,
            converged=score.score >= self.threshold,
        )


class VerifierLoop(Generic[In, Out]):
    generator: ClassVar[Agent] = Reasoner(input=Task, output=Answer)
    critic: ClassVar[Agent] = Critic()

    def __init__(
        self,
        context: str = "",
        *,
        threshold: float = 0.8,
        max_iter: int = 3,
    ) -> None:
        if max_iter < 1:
            raise ValueError(f"max_iter must be >= 1, got {max_iter}")

        cls = type(self)
        self.generator = cls.generator.clone(context=context)
        self.critic = cls.critic.clone(context=context)

        self.context = context
        self.threshold = threshold
        self.max_iter = max_iter

    async def run(self, x: In) -> Out:
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={"max_iter": self.max_iter, "threshold": self.threshold},
                started_at=started,
            )
            try:
                if _TRACER.get() is None:
                    await _ensure_built(self.generator, self.critic)

                step = _VerifyStep(
                    generator=self.generator,
                    critic=self.critic,
                    threshold=self.threshold,
                    algorithm_path=path,
                )
                loop = Loop(
                    step,
                    input=_VerifierState,
                    output=_VerifierState,
                    n_loops=self.max_iter,
                )
                final = await _run_loop(loop, _VerifierState(request=x))

                candidate = final.candidate
                if candidate is None:
                    candidate = self.generator.output.model_construct()

                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "iterations": final.iterations,
                        "score": final.score,
                        "converged": final.converged,
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return candidate  # type: ignore[return-value]
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise


__all__ = ["VerifierLoop"]
