"""Talker composite: safeguard → turn-taker → persona pipeline."""

from __future__ import annotations

from pydantic import BaseModel

from ....core.agent import Agent
from ...core.pipelines import Router, Sequential
from ..schemas import SafeguardVerdict, StyledUtterance, Utterance
from .persona import Persona
from .refusal import RefusalLeaf
from .safeguard import Safeguard
from .turn_taker import TurnTaker


class _TurnGate(Agent[Utterance, Utterance]):
    input = Utterance
    output = Utterance
    config = None

    def __init__(self, turn_taker: Agent) -> None:
        super().__init__(config=None, input=Utterance, output=Utterance)
        self.turn_taker = turn_taker

    async def forward(self, x: Utterance) -> Utterance:  # type: ignore[override]
        await self.turn_taker(x)
        return x


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
        self._rebuild_router()

    def __setattr__(self, name: str, value) -> None:
        super().__setattr__(name, value)
        if name in {"safeguard", "turn_taker", "persona", "refusal"}:
            keys = {"safeguard", "turn_taker", "persona", "refusal"}
            if keys.issubset(self.__dict__):
                self._rebuild_router()

    def _rebuild_router(self) -> None:
        self._turn_gate = _TurnGate(self.turn_taker)
        self.allow = Sequential(
            self._turn_gate,
            self.persona,
            input=Utterance,
            output=StyledUtterance,
        )
        self.router = Router(
            router=self.safeguard,
            branches={
                "allow": self.allow,
                "block": self.refusal,
            },
            input=Utterance,
            output=StyledUtterance,
            branch_input=self._branch_input,
        )

    def _branch_input(
        self,
        x: Utterance,
        choice: BaseModel,
        branch: Agent,
    ) -> BaseModel:
        if branch.input is SafeguardVerdict:
            return choice
        return x

    async def forward(self, x: Utterance) -> StyledUtterance:  # type: ignore[override]
        return (await self.router(x)).response
