"""VerifierAgent: typed Agent wrapper around the VerifierLoop algorithm.

Exposes the generate-until-verified loop as an ``Agent[Task, Answer]``
so it can be dropped into any ``Pipeline`` like any other leaf.
"""

from __future__ import annotations

from typing import Any

from ...core.agent import Agent
from ...core.config import Configuration
from .components import Critic, Reasoner
from .schemas import Answer, Task


class VerifierAgent(Agent[Task, Answer]):
    """Pre-wired VerifierLoop composition as a single typed agent.

    Wraps :class:`~operad.algorithms.VerifierLoop`. Accepts custom
    ``generator`` and ``verifier`` components as kwargs; if omitted,
    defaults are constructed using ``config``.

    The ``verifier`` kwarg maps to the loop's internal ``critic`` slot
    (VerifierLoop uses the name ``critic``; the agent surface uses
    ``verifier`` to match the brief's API spec).

    Components are registered as children so ``build()`` wires and
    type-checks them.
    """

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
        super().__init__(config=None, input=Task, output=Answer)

        self.generator: Agent[Any, Any] = generator or Reasoner(
            config=config, input=Task, output=Answer
        )
        # "verifier" in the agent API corresponds to "critic" in VerifierLoop
        self.verifier: Agent[Any, Any] = verifier or Critic(config=config)

        from ...algorithms.verifier_loop import VerifierLoop

        self._algo: VerifierLoop[Task, Answer] = VerifierLoop(
            threshold=threshold,
            max_iter=max_iter,
        )
        self._algo.generator = self.generator
        self._algo.critic = self.verifier

    async def forward(self, x: Task) -> Answer:  # type: ignore[override]
        return await self._algo.run(x)


__all__ = ["VerifierAgent"]
