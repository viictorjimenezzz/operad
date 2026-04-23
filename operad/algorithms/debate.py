"""Debate: N proposers, critique rounds, one synthesiser.

Each proposer generates an independent proposal. In every round, the
critic reviews each proposal in the context of the full record (other
proposals and critiques so far). After `rounds` rounds, the synthesiser
reads the accumulated `DebateRecord` and emits the final answer.
"""

from __future__ import annotations

import asyncio
from typing import Any, Generic

from pydantic import BaseModel, ConfigDict, Field

from ..core.agent import Agent, In, Out


class Proposal(BaseModel):
    content: Any = Field(
        default=None,
        description="A proposer's suggested answer.",
    )
    author: str = Field(
        default="",
        description="Identifier of the proposer that produced this content.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Critique(BaseModel):
    target_author: str = Field(
        default="",
        description="Which proposer's content this critique addresses.",
    )
    comments: str = Field(
        default="",
        description="Natural-language assessment.",
    )
    score: float = Field(
        default=0.0,
        description="Higher-is-better numeric score for the targeted proposal.",
    )


class DebateRecord(BaseModel, Generic[In]):
    request: In | None = Field(
        default=None,
        description="The original request every proposer answered.",
    )
    proposals: list[Proposal] = Field(default_factory=list)
    critiques: list[Critique] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DebateTurn(BaseModel, Generic[In]):
    """What the critic sees on each turn: full record plus the focal proposal."""

    record: DebateRecord[In] | None = Field(default=None)
    focus: Proposal | None = Field(
        default=None,
        description="The proposal the critic should comment on this turn.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Debate(Generic[In, Out]):
    def __init__(
        self,
        proposers: list[Agent[In, Proposal]],
        critic: Agent[DebateTurn[In], Critique],
        synthesizer: Agent[DebateRecord[In], Out],
        *,
        rounds: int = 1,
    ) -> None:
        if not proposers:
            raise ValueError("proposers must not be empty")
        if rounds < 0:
            raise ValueError(f"rounds must be >= 0, got {rounds}")
        self.proposers = proposers
        self.critic = critic
        self.synthesizer = synthesizer
        self.rounds = rounds

    async def run(self, x: In) -> Out:
        proposals: list[Proposal] = list(
            await asyncio.gather(*(p(x) for p in self.proposers))
        )
        record: DebateRecord[In] = DebateRecord(
            request=x, proposals=proposals, critiques=[]
        )
        for _ in range(self.rounds):
            critiques = await asyncio.gather(
                *(
                    self.critic(DebateTurn(record=record, focus=p))
                    for p in proposals
                )
            )
            record.critiques.extend(critiques)
        return await self.synthesizer(record)
