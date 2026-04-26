"""SelfRefine: iterative generate -> reflect -> refine."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, ClassVar, Generic

from pydantic import BaseModel, Field

from ..agents.reasoning.components import Reflector
from ..agents.reasoning.components.reasoner import Reasoner
from ..agents.reasoning.schemas import Answer, Reflection, ReflectionInput, Task
from ..core.agent import Agent, In, Out, _TRACER
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


class RefineInput(BaseModel):
    """Typed request passed to the refiner after a failed reflection."""

    original_request: str = Field(description="The user's original ask.")
    candidate_answer: str = Field(description="The draft to improve.")
    critique: str = Field(description="Specific deficiencies to address.")


@dataclass
class SelfRefineState:
    iter_index: int
    draft: Any
    reflection: Reflection


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


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
    unique = list({id(a): a for a in agents}.values())
    pending = [a.abuild() for a in unique if not a._built]
    if pending:
        await asyncio.gather(*pending)


# ---------------------------------------------------------------------------
# Algorithm.
# ---------------------------------------------------------------------------


class SelfRefine(Generic[In, Out]):
    """Generate an initial draft, reflect on it, and refine until accepted."""

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
        self.stop_when = stop_when or _default_stop

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

                draft: BaseModel | None = None
                reflection: Reflection | None = None
                converged = False
                iterations = 0

                for iter_index in range(self.max_iter):
                    if iter_index == 0:
                        draft = (await self.generator(x)).response
                    else:
                        draft = (
                            await self.refiner(
                                RefineInput(
                                    original_request=str(x),
                                    candidate_answer=_as_text(draft),
                                    critique="; ".join(
                                        reflection.deficiencies
                                        if reflection is not None
                                        else []
                                    ),
                                )
                            )
                        ).response
                        await emit_algorithm_event(
                            "iteration",
                            algorithm_path=path,
                            payload={
                                "iter_index": iter_index,
                                "phase": "refine",
                                "text": _as_text(draft),
                            },
                        )

                    reflection = (
                        await self.reflector(
                            ReflectionInput(
                                original_request=str(x),
                                candidate_answer=_as_text(draft),
                            )
                        )
                    ).response
                    critique_summary = (
                        "; ".join(reflection.deficiencies)
                        if reflection.deficiencies
                        else ""
                    )
                    await emit_algorithm_event(
                        "iteration",
                        algorithm_path=path,
                        payload={
                            "iter_index": iter_index,
                            "phase": "reflect",
                            "score": reflection.score,
                            "needs_revision": reflection.needs_revision,
                            "critique_summary": critique_summary,
                            "text": _as_text(draft),
                        },
                    )

                    iterations = iter_index + 1
                    state = SelfRefineState(
                        iter_index=iter_index,
                        draft=draft,
                        reflection=reflection,
                    )
                    converged = self.stop_when(state)
                    if converged:
                        break

                if draft is None:
                    draft = self.generator.output.model_construct()

                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={"iterations": iterations, "converged": converged},
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
