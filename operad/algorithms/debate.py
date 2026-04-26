"""Debate: N proposers, critique rounds, one synthesizer."""

from __future__ import annotations

import asyncio
import time
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from ..agents.debate.components import DebateCritic, Proposer, Synthesizer
from ..agents.debate.schemas import (
    Critique,
    DebateRecord,
    DebateTopic,
    DebateTurn,
    Proposal,
)
from ..agents.reasoning.schemas import Answer
from ..core.agent import Agent, _TRACER
from ..core.flow import Parallel
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


# ---------------------------------------------------------------------------
# Domain schemas.
# ---------------------------------------------------------------------------


class ProposalBatch(BaseModel):
    """Outputs from the proposer fanout, in proposer-index order."""

    proposals: list[Proposal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _ensure_built(*agents: Agent[Any, Any]) -> None:
    pending = [a.abuild() for a in agents if not a._built]
    if pending:
        await asyncio.gather(*pending)


# ---------------------------------------------------------------------------
# Algorithm.
# ---------------------------------------------------------------------------


class Debate:
    """Run proposers in parallel, critique each proposal, then synthesize."""

    proposers: ClassVar[list[Agent]] = [Proposer(), Proposer(), Proposer()]
    critic: ClassVar[Agent] = DebateCritic()
    synthesizer: ClassVar[Agent] = Synthesizer()

    def __init__(
        self,
        context: str = "",
        *,
        rounds: int = 1,
    ) -> None:
        if rounds < 0:
            raise ValueError(f"rounds must be >= 0, got {rounds}")

        cls = type(self)
        if not cls.proposers:
            raise ValueError("proposers class attribute must not be empty")

        self.proposers = [p.clone(context=context) for p in cls.proposers]
        self.critic = cls.critic.clone(context=context)
        self.synthesizer = cls.synthesizer.clone(context=context)

        self.context = context
        self.rounds = rounds

    async def run(self, x: DebateTopic) -> Answer:
        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={"proposers": len(self.proposers), "rounds": self.rounds},
                started_at=started,
            )
            try:
                if _TRACER.get() is None:
                    await _ensure_built(*self.proposers, self.synthesizer)

                fanout = Parallel(
                    {f"proposer_{i}": p for i, p in enumerate(self.proposers)},
                    input=DebateTopic,
                    output=ProposalBatch,
                    combine=lambda results: ProposalBatch(
                        proposals=[
                            results[f"proposer_{i}"]
                            for i in range(len(self.proposers))
                        ]
                    ),
                )
                proposals = (await fanout.forward(x)).proposals
                record = DebateRecord(request=x, proposals=proposals, critiques=[])

                for round_index in range(self.rounds):
                    critics = [self.critic.clone() for _ in proposals]
                    if _TRACER.get() is None:
                        await _ensure_built(*critics)

                    raw_critiques = await asyncio.gather(
                        *(
                            critics[i](DebateTurn(record=record, focus=proposal))
                            for i, proposal in enumerate(proposals)
                        )
                    )
                    new_critiques: list[Critique] = [
                        r.response for r in raw_critiques
                    ]
                    await emit_algorithm_event(
                        "round",
                        algorithm_path=path,
                        payload={
                            "round_index": round_index,
                            "proposals": [
                                p.model_dump(mode="json") for p in proposals
                            ],
                            "critiques": [
                                c.model_dump(mode="json") for c in new_critiques
                            ],
                            "scores": [c.score for c in new_critiques],
                        },
                    )
                    record = DebateRecord(
                        request=x,
                        proposals=proposals,
                        critiques=[*record.critiques, *new_critiques],
                    )

                result = (await self.synthesizer(record)).response
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={"rounds": self.rounds},
                    started_at=started,
                    finished_at=time.time(),
                )
                return result
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise


__all__ = ["Debate"]
