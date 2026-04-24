"""Best-of-N: sample N candidates, pick the one the judge prefers.

`BestOfN` is an algorithm, not an Agent. It orchestrates a generator and
a judge (both of which *are* Agents) to close a metric-driven loop. Its
``run(x)`` method is typed `In -> Out` for the common case but it
deliberately does not inherit from `Agent`: algorithms have their own
API shape (e.g. a future `Evolutionary.run(template) -> Agent`), and
forcing them all into `__call__(x: In) -> Out` loses information.

To embed a `BestOfN` inside a composite Agent, wrap it in a small leaf
that calls ``await best.run(x)`` from its own ``forward``.
"""

from __future__ import annotations

import asyncio
import time
from typing import Generic

from ..core.agent import Agent, In, Out
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
from .judge import Candidate, Score


class BestOfN(Generic[In, Out]):
    """Generate N candidates with `generator`, score each with `judge`,
    return the highest-scored one.

    `judge` is an ``Agent[Candidate[In, Out], Score]``: it sees both the
    original request and a candidate and returns a ``Score``.
    """

    def __init__(
        self,
        generator: Agent[In, Out],
        judge: Agent[Candidate[In, Out], Score],
        *,
        n: int,
    ) -> None:
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        self.generator = generator
        self.judge = judge
        self.n = n

    async def run(self, x: In) -> Out:
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={"n": self.n},
                started_at=started,
            )
            try:
                # Concurrent calls to one Agent corrupt the strands-owned conversation
                # history, so give each candidate its own instance.
                gens = [self.generator] + [self.generator.clone() for _ in range(self.n - 1)]
                judges = [self.judge] + [self.judge.clone() for _ in range(self.n - 1)]
                if self.n > 1:
                    await asyncio.gather(*(a.abuild() for a in gens[1:] + judges[1:]))

                gen_outputs = await asyncio.gather(*(gens[i](x) for i in range(self.n)))
                candidates: list[Out] = [g.response for g in gen_outputs]
                judge_outputs = await asyncio.gather(
                    *(judges[i](Candidate(input=x, output=candidates[i])) for i in range(self.n))
                )
                scores: list[Score] = [j.response for j in judge_outputs]
                for i, s in enumerate(scores):
                    await emit_algorithm_event(
                        "candidate",
                        algorithm_path=path,
                        payload={"candidate_index": i, "score": s.score},
                    )
                best = max(range(self.n), key=lambda i: scores[i].score)
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={"best_index": best, "score": scores[best].score},
                    started_at=started,
                    finished_at=time.time(),
                )
                return candidates[best]
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise
