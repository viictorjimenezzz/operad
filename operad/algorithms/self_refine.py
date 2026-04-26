"""SelfRefine: iterative generate → reflect → refine loop.

The generator is called once to produce an initial draft; the reflector
inspects it and either approves or flags deficiencies; the refiner (or
generator again, in on-policy mode) rewrites the draft.  The loop
repeats up to ``max_iter`` times and exits early when ``stop_when``
returns ``True`` (default: when the reflector says no revision is
needed).

Components are **class-level defaults**; callers supply only the
algorithm's own knobs.  Swap components via a subclass or by assigning
to instance attributes after construction (same idiom as VerifierLoop).

Reference: Madaan et al., "Self-Refine: Iterative Refinement with
Self-Feedback", NeurIPS 2023.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic

from pydantic import BaseModel, Field

from ..agents.core.pipelines import Loop
from ..agents.reasoning.components import Reflector
from ..agents.reasoning.components.reasoner import Reasoner
from ..agents.reasoning.schemas import Answer, Reflection, ReflectionInput, Task
from ..core.agent import Agent, In, Out, _TRACER
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


class RefineInput(BaseModel):
    original_request: str = Field(description="The user's original ask.")
    candidate_answer: str = Field(description="The draft to improve.")
    critique: str = Field(description="Specific deficiencies to address.")


@dataclass
class SelfRefineState:
    iter_index: int
    draft: Any
    reflection: Reflection


def _default_stop(state: SelfRefineState) -> bool:
    return not state.reflection.needs_revision


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


class _SelfRefineRuntime(BaseModel):
    request: BaseModel | None = None
    draft: BaseModel | None = None
    reflection: Reflection | None = None
    iter_index: int = 0
    converged: bool = False


class _SelfRefineStep(Agent[_SelfRefineRuntime, _SelfRefineRuntime]):
    input = _SelfRefineRuntime
    output = _SelfRefineRuntime

    def __init__(
        self,
        *,
        generator: Agent[Any, Any],
        refiner: Agent[Any, Any],
        reflector: Agent[Any, Any],
        stop_when: Callable[[SelfRefineState], bool],
        algorithm_path: str,
    ) -> None:
        super().__init__(config=None, input=_SelfRefineRuntime, output=_SelfRefineRuntime)
        self.generator = generator
        self.refiner = refiner
        self.reflector = reflector
        self.stop_when = stop_when
        self.algorithm_path = algorithm_path

    async def forward(self, x: _SelfRefineRuntime) -> _SelfRefineRuntime:  # type: ignore[override]
        if x.converged:
            return x

        request = x.request
        if request is None:
            request = self.generator.input.model_construct()

        iter_index = x.iter_index
        draft = x.draft
        reflection = x.reflection

        if iter_index == 0:
            draft = (await self.generator(request)).response
        else:
            refine_input = RefineInput(
                original_request=str(request),
                candidate_answer=str(draft),
                critique="; ".join((reflection.deficiencies if reflection is not None else [])),
            )
            draft = (await self.refiner(refine_input)).response
            await emit_algorithm_event(
                "iteration",
                algorithm_path=self.algorithm_path,
                payload={
                    "iter_index": iter_index,
                    "phase": "refine",
                    "text": _as_text(draft),
                },
            )

        reflection = (
            await self.reflector(
                ReflectionInput(
                    original_request=str(request),
                    candidate_answer=str(draft),
                )
            )
        ).response
        critique_summary = "; ".join(reflection.deficiencies) if reflection.deficiencies else ""
        await emit_algorithm_event(
            "iteration",
            algorithm_path=self.algorithm_path,
            payload={
                "iter_index": iter_index,
                "phase": "reflect",
                "score": reflection.score,
                "needs_revision": reflection.needs_revision,
                "critique_summary": critique_summary,
                "text": _as_text(draft),
            },
        )

        state = SelfRefineState(iter_index=iter_index, draft=draft, reflection=reflection)
        return _SelfRefineRuntime(
            request=request,
            draft=draft,
            reflection=reflection,
            iter_index=iter_index + 1,
            converged=self.stop_when(state),
        )


class SelfRefine(Generic[In, Out]):
    generator: ClassVar[Agent] = Reasoner(input=Task, output=Answer)
    reflector: ClassVar[Agent] = Reflector()
    refiner: ClassVar[Agent] = Reasoner(input=RefineInput, output=Answer)

    def __init__(
        self,
        context: str = "",
        *,
        max_iter: int = 3,
        stop_when: Callable[[SelfRefineState], bool] | None = None,
        on_policy: bool = False,
    ) -> None:
        if max_iter < 1:
            raise ValueError(f"max_iter must be >= 1, got {max_iter}")

        cls = type(self)
        self.generator = cls.generator.clone(context=context)
        self.reflector = cls.reflector.clone(context=context)
        self.refiner = self.generator if on_policy else cls.refiner.clone(context=context)

        self.context = context
        self.max_iter = max_iter
        self.stop_when: Callable[[SelfRefineState], bool] = stop_when or _default_stop

    async def run(self, x: In) -> Out:
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={"max_iter": self.max_iter},
                started_at=started,
            )
            try:
                if _TRACER.get() is None:
                    await _ensure_built(self.generator, self.reflector, self.refiner)

                step = _SelfRefineStep(
                    generator=self.generator,
                    refiner=self.refiner,
                    reflector=self.reflector,
                    stop_when=self.stop_when,
                    algorithm_path=path,
                )
                loop = Loop(
                    step,
                    input=_SelfRefineRuntime,
                    output=_SelfRefineRuntime,
                    n_loops=self.max_iter,
                )
                final = await _run_loop(loop, _SelfRefineRuntime(request=x))

                draft = final.draft
                if draft is None:
                    draft = self.generator.output.model_construct()

                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "iterations": final.iter_index,
                        "converged": final.converged,
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return draft  # type: ignore[return-value]
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise


__all__ = ["RefineInput", "SelfRefine", "SelfRefineState"]
