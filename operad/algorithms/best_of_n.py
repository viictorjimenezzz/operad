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
from typing import Generic

from ..core.agent import Agent, In, Out
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
        gen_outputs = await asyncio.gather(
            *(self.generator(x) for _ in range(self.n))
        )
        candidates: list[Out] = [g.response for g in gen_outputs]
        judge_outputs = await asyncio.gather(
            *(self.judge(Candidate(input=x, output=c)) for c in candidates)
        )
        scores: list[Score] = [j.response for j in judge_outputs]
        best = max(range(self.n), key=lambda i: scores[i].score)
        return candidates[best]
