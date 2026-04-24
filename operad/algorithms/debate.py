"""Debate: N proposers, critique rounds, one synthesiser.

Each proposer generates an independent proposal. In every round, the
critic reviews each proposal in the context of the full record (other
proposals and critiques so far). After ``rounds`` rounds, the
synthesiser reads the accumulated ``DebateRecord`` and emits the final
answer.

Components are **class-level defaults** so callers typically supply
only the algorithm's own knobs (``context``, ``rounds``); swap in
different components via a subclass.
"""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar

from ..agents.debate.components import DebateCritic, Proposer, Synthesizer
from ..agents.debate.schemas import (
    Critique,
    DebateContext,
    DebateRecord,
    DebateTurn,
    Proposal,
)
from ..agents.reasoning.schemas import Answer
from ..core.agent import Agent
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


class Debate:
    """Multi-proposer debate with critique rounds and a final synthesis.

    Runs ``len(proposers)`` proposers in parallel, then ``rounds``
    rounds of critiques (each round critiques every current proposal
    once), then one synthesis pass over the full accumulated record.
    """

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

        # Distinct clones per proposer — shared strands history across
        # concurrent calls corrupts structured output.
        self.proposers = [p.clone(context=context) for p in cls.proposers]
        self.critic = cls.critic.clone(context=context)
        self.synthesizer = cls.synthesizer.clone(context=context)

        self.context = context
        self.rounds = rounds

    async def run(self, x: DebateContext) -> Answer:
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
                raw_proposals = await asyncio.gather(
                    *(p(x) for p in self.proposers)
                )
                proposals: list[Proposal] = [r.response for r in raw_proposals]
                record: DebateRecord = DebateRecord(
                    request=x, proposals=proposals, critiques=[]
                )
                # Each critique in a round needs its own critic clone so the
                # concurrent gather does not share strands history.
                for round_index in range(self.rounds):
                    critics = [self.critic] + [
                        self.critic.clone() for _ in range(len(proposals) - 1)
                    ]
                    if len(proposals) > 1:
                        await asyncio.gather(
                            *(c.abuild() for c in critics[1:])
                        )
                    raw_critiques = await asyncio.gather(
                        *(
                            critics[i](DebateTurn(record=record, focus=p))
                            for i, p in enumerate(proposals)
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
                    record.critiques.extend(new_critiques)
                result: Answer = (await self.synthesizer(record)).response
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
