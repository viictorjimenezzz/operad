"""DebateAgent: typed Agent wrapper around the Debate algorithm."""

from __future__ import annotations

from typing import Any

from ...core.agent import Agent
from ...core.config import Configuration
from ..debate.schemas import DebateTopic
from .schemas import Answer


class DebateAgent(Agent[DebateTopic, Answer]):
    """Expose the multi-proposer debate algorithm as a typed agent."""

    input = DebateTopic
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
        super().__init__(config=None, input=DebateTopic, output=Answer)

        from ..debate.components import DebateCritic, Proposer, Synthesizer

        debate_proposers: list[Agent[Any, Any]] = proposers or [
            Proposer(config=config),
            Proposer(config=config),
            Proposer(config=config),
        ]
        for i, proposer in enumerate(debate_proposers):
            setattr(self, f"proposer_{i}", proposer)
        self.n_proposers = len(debate_proposers)

        self.debate_critic: Agent[Any, Any] = critic or DebateCritic(config=config)
        self.synthesizer: Agent[Any, Any] = synthesizer or Synthesizer(config=config)

        from ...algorithms.debate import Debate

        self.debate = Debate(rounds=rounds)
        self.debate.proposers = [
            getattr(self, f"proposer_{i}") for i in range(self.n_proposers)
        ]
        self.debate.critic = self.debate_critic
        self.debate.synthesizer = self.synthesizer

    async def forward(self, x: DebateTopic) -> Answer:  # type: ignore[override]
        return await self.debate.run(x)


__all__ = ["DebateAgent"]
