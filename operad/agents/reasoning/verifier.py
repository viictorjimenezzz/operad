"""VerifierAgent: typed generate-until-verified reasoning agent."""

from __future__ import annotations

import time
from typing import Any

from ...core.agent import Agent
from ...core.config import Configuration
from ...runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
from .components import Critic, Reasoner
from .schemas import Answer, Candidate, Score, Task


def _as_text(x: object) -> str:
    answer = getattr(x, "answer", None)
    if isinstance(answer, str):
        return answer
    return str(x)


class VerifierAgent(Agent[Task, Answer]):
    """Generate candidates until the verifier score clears ``threshold``."""

    input = Task
    output = Answer

    def __init__(
        self,
        *,
        config: Configuration | None = None,
        generator: Agent[Any, Any] | None = None,
        verifier: Agent[Any, Any] | None = None,
        threshold: float = 0.8,
        max_iter: int = 3,
    ) -> None:
        if max_iter < 1:
            raise ValueError(f"max_iter must be >= 1, got {max_iter}")

        super().__init__(config=None, input=Task, output=Answer)

        self.generator: Agent[Any, Any] = generator or Reasoner(
            config=config, input=Task, output=Answer
        )
        self.verifier: Agent[Any, Any] = verifier or Critic(config=config)
        self.threshold = threshold
        self.max_iter = max_iter

    async def forward(self, x: Task) -> Answer:  # type: ignore[override]
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
                candidate = Answer.model_construct()
                score: Score | None = None
                for iter_index in range(self.max_iter):
                    candidate = (await self.generator(x)).response
                    score = (
                        await self.verifier(Candidate(input=x, output=candidate))
                    ).response
                    await emit_algorithm_event(
                        "iteration",
                        algorithm_path=path,
                        payload={
                            "iter_index": iter_index,
                            "phase": "verify",
                            "score": score.score,
                            "text": _as_text(candidate),
                        },
                    )
                    if score.score >= self.threshold:
                        break

                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "iterations": iter_index + 1,
                        "score": None if score is None else score.score,
                        "converged": score is not None and score.score >= self.threshold,
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return candidate
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise


__all__ = ["VerifierAgent"]
