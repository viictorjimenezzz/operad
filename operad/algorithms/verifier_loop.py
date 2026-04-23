"""VerifierLoop: regenerate until a critic is satisfied.

The generator is called up to `max_iter` times; each candidate is scored
by the critic (an `Agent[Candidate[In, Out], Score]`). The loop exits
early the first time a score clears `threshold`, otherwise it returns
the last candidate. Randomisation, if any, lives on the generator's
sampling config — not here.
"""

from __future__ import annotations

from typing import Generic

from ..core.agent import Agent, In, Out
from .judge import Candidate, Score


class VerifierLoop(Generic[In, Out]):
    def __init__(
        self,
        generator: Agent[In, Out],
        critic: Agent[Candidate[In, Out], Score],
        *,
        threshold: float = 0.8,
        max_iter: int = 3,
    ) -> None:
        if max_iter < 1:
            raise ValueError(f"max_iter must be >= 1, got {max_iter}")
        self.generator = generator
        self.critic = critic
        self.threshold = threshold
        self.max_iter = max_iter

    async def run(self, x: In) -> Out:
        last: Out | None = None
        for _ in range(self.max_iter):
            last = (await self.generator(x)).response
            score = (await self.critic(Candidate(input=x, output=last))).response
            if score.score >= self.threshold:
                return last
        assert last is not None  # max_iter >= 1 guaranteed at construction
        return last
