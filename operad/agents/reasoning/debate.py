"""DebateAgent: typed Agent wrapper around the Debate algorithm.

Exposes the multi-proposer / critic-round / synthesizer orchestration
as an ``Agent[DebateContext, Answer]`` so it can be dropped into any
``Sequential`` like any other leaf.
"""

from __future__ import annotations

from typing import Any

from ...core.agent import Agent
from ...core.config import Configuration
from ..debate.schemas import DebateContext
from .schemas import Answer


class DebateAgent(Agent[DebateContext, Answer]):
    """Pre-wired Debate composition as a single typed agent.

    Wraps :class:`~operad.algorithms.Debate`. Accepts custom components
    as kwargs; if omitted, three default :class:`~operad.agents.debate.Proposer`
    instances, one :class:`~operad.agents.debate.DebateCritic`, and one
    :class:`~operad.agents.debate.Synthesizer` are created using ``config``.

    Components are registered as children so ``build()`` wires and
    type-checks them.  Two ``DebateAgent`` instances with different
    critics hash differently because their child hashes differ.
    """

    input = DebateContext
    output = Answer

    def __init__(
        self,
        *,
        config: Configuration | None = None,
        proposers: list[Agent[Any, Any]] | None = None,
        critic: Agent[Any, Any] | None = None,
        synthesizer: Agent[Any, Any] | None = None,
        rounds: int = 1,
    ) -> None:
        super().__init__(config=None, input=DebateContext, output=Answer)

        # Deferred to break the reasoning/__init__ → debate.py → debate.components
        # → proposer.py → reasoning.components → reasoning/__init__ circular.
        from ..debate.components import DebateCritic, Proposer, Synthesizer

        _proposers: list[Agent[Any, Any]] = proposers or [
            Proposer(config=config),
            Proposer(config=config),
            Proposer(config=config),
        ]
        for i, p in enumerate(_proposers):
            setattr(self, f"proposer_{i}", p)  # auto-registers in _children
        self._n_proposers = len(_proposers)

        self.debate_critic: Agent[Any, Any] = critic or DebateCritic(config=config)
        self.synthesizer: Agent[Any, Any] = synthesizer or Synthesizer(config=config)

        from ...algorithms.debate import Debate

        # Wire the underlying algorithm with our (not-yet-built) children.
        # Debate.__init__ clones class-level defaults; we immediately replace
        # them with our instances so run() uses our pre-built children.
        self._algo = Debate(rounds=rounds)
        self._algo.proposers = [
            getattr(self, f"proposer_{i}") for i in range(self._n_proposers)
        ]
        self._algo.critic = self.debate_critic
        self._algo.synthesizer = self.synthesizer

    async def forward(self, x: DebateContext) -> Answer:  # type: ignore[override]
        return await self._algo.run(x)  # type: ignore[return-value]


__all__ = ["DebateAgent"]
