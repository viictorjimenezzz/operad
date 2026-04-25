"""Talker composite: safeguard → turn-taker → persona pipeline."""

from __future__ import annotations

from ....core.agent import Agent, _TRACER
from ..schemas import SafeguardVerdict, StyledUtterance, Utterance
from .persona import Persona
from .refusal import RefusalLeaf
from .safeguard import Safeguard
from .turn_taker import TurnTaker


class Talker(Agent[Utterance, StyledUtterance]):
    """Route a user message through safety, turn-gating, and persona styling.

    On the allow path: safeguard → turn_taker → persona → StyledUtterance.
    On the block path: safeguard → refusal → StyledUtterance.
    """

    input = Utterance
    output = StyledUtterance

    def __init__(self, *, config, **kwargs) -> None:  # type: ignore[override]
        super().__init__(config=config, input=Utterance, output=StyledUtterance, **kwargs)
        self.safeguard = Safeguard(config=config)
        self.turn_taker = TurnTaker(config=config)
        self.persona = Persona(config=config)
        self.refusal = RefusalLeaf()

    async def forward(self, x: Utterance) -> StyledUtterance:  # type: ignore[override]
        # During symbolic build tracing visit every child so all edges are recorded.
        if _TRACER.get() is not None:
            await self.safeguard(x)
            await self.turn_taker(x)
            await self.persona(x)
            await self.refusal(SafeguardVerdict())
            return StyledUtterance()

        verdict: SafeguardVerdict = (await self.safeguard(x)).response
        if verdict.label == "block":
            return (await self.refusal(verdict)).response
        await self.turn_taker(x)
        return (await self.persona(x)).response
