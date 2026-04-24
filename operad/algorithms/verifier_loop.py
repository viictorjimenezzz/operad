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

import time
from typing import ClassVar, Generic

from ..agents.reasoning.components import Critic, Reasoner
from ..agents.reasoning.schemas import Answer, Candidate, Task
from ..core.agent import Agent, In, Out
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


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
                last: Out | None = None
                last_score: float | None = None
                for iter_index in range(self.max_iter):
                    last = (await self.generator(x)).response
                    score = (
                        await self.critic(Candidate(input=x, output=last))
                    ).response
                    last_score = score.score
                    await emit_algorithm_event(
                        "iteration",
                        algorithm_path=path,
                        payload={
                            "iter_index": iter_index,
                            "phase": "verify",
                            "score": score.score,
                        },
                    )
                    if score.score >= self.threshold:
                        await emit_algorithm_event(
                            "algo_end",
                            algorithm_path=path,
                            payload={
                                "iterations": iter_index + 1,
                                "score": score.score,
                                "converged": True,
                            },
                            started_at=started,
                            finished_at=time.time(),
                        )
                        return last
                assert last is not None  # max_iter >= 1 guaranteed at construction
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "iterations": self.max_iter,
                        "score": last_score,
                        "converged": False,
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return last
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
