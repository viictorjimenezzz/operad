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
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from ..agents.debate.components import DebateCritic, Proposer, Synthesizer
from ..agents.debate.schemas import (
    Critique,
    DebateContext,
    DebateRecord,
    DebateTurn,
    Proposal,
)
from ..agents.core.pipelines import Loop, Parallel, Sequential
from ..agents.reasoning.schemas import Answer
from ..core.agent import Agent, _TRACER
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event


async def _ensure_built(*agents: Agent[Any, Any]) -> None:
    pending = [a.abuild() for a in agents if not a._built]
    if pending:
        await asyncio.gather(*pending)


async def _invoke_stage(stage: Agent[Any, Any], x: BaseModel) -> BaseModel:
    if stage._built:
        return (await stage(x)).response
    return await stage.forward(x)


async def _run_sequential(seq: Sequential[Any, Any], x: BaseModel) -> BaseModel:
    current = x
    for stage in seq._stages:
        current = await _invoke_stage(stage, current)
    return current


async def _run_loop(loop: Loop[Any], x: BaseModel) -> BaseModel:
    current = x
    for _ in range(loop.n_loops):
        for stage in loop._stages:
            current = await _invoke_stage(stage, current)
    return current


class _ProposalBatch(BaseModel):
    proposals: list[Proposal] = Field(default_factory=list)


class _InitDebateRecord(Agent[DebateContext, DebateRecord]):
    input = DebateContext
    output = DebateRecord

    def __init__(self, *, proposer_fanout: Parallel[DebateContext, _ProposalBatch]) -> None:
        super().__init__(config=None, input=DebateContext, output=DebateRecord)
        self.proposer_fanout = proposer_fanout

    async def forward(self, x: DebateContext) -> DebateRecord:  # type: ignore[override]
        batch = await self.proposer_fanout.forward(x)
        return DebateRecord(request=x, proposals=batch.proposals, critiques=[])


class _DebateRound(Agent[DebateRecord, DebateRecord]):
    input = DebateRecord
    output = DebateRecord

    def __init__(self, *, critic: Agent[Any, Any], algorithm_path: str) -> None:
        super().__init__(config=None, input=DebateRecord, output=DebateRecord)
        self.critic = critic
        self.algorithm_path = algorithm_path
        self._round_index = 0

    def reset(self) -> None:
        self._round_index = 0

    async def forward(self, x: DebateRecord) -> DebateRecord:  # type: ignore[override]
        proposals = list(x.proposals)
        critics = [self.critic] + [
            self.critic.clone() for _ in range(max(len(proposals) - 1, 0))
        ]
        if _TRACER.get() is None:
            await _ensure_built(*critics[1:])

        raw_critiques = await asyncio.gather(
            *(
                critics[i](DebateTurn(record=x, focus=p))
                for i, p in enumerate(proposals)
            )
        )
        new_critiques: list[Critique] = [r.response for r in raw_critiques]

        await emit_algorithm_event(
            "round",
            algorithm_path=self.algorithm_path,
            payload={
                "round_index": self._round_index,
                "proposals": [p.model_dump(mode="json") for p in proposals],
                "critiques": [c.model_dump(mode="json") for c in new_critiques],
                "scores": [c.score for c in new_critiques],
            },
        )
        self._round_index += 1
        return DebateRecord(
            request=x.request,
            proposals=proposals,
            critiques=[*x.critiques, *new_critiques],
        )


class _CritiqueRounds(Agent[DebateRecord, DebateRecord]):
    input = DebateRecord
    output = DebateRecord

    def __init__(
        self,
        *,
        critic: Agent[Any, Any],
        rounds: int,
        algorithm_path: str,
    ) -> None:
        super().__init__(config=None, input=DebateRecord, output=DebateRecord)
        self._round = _DebateRound(critic=critic, algorithm_path=algorithm_path)
        self._loop: Loop[DebateRecord] | None = None
        if rounds > 0:
            self._loop = Loop(
                self._round,
                input=DebateRecord,
                output=DebateRecord,
                n_loops=rounds,
            )

    async def forward(self, x: DebateRecord) -> DebateRecord:  # type: ignore[override]
        if self._loop is None:
            return x
        self._round.reset()
        out = await _run_loop(self._loop, x)
        return out  # type: ignore[return-value]


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
                if _TRACER.get() is None:
                    await _ensure_built(*self.proposers, self.critic, self.synthesizer)

                proposer_fanout = Parallel(
                    {
                        f"proposer_{i}": p
                        for i, p in enumerate(self.proposers)
                    },
                    input=DebateContext,
                    output=_ProposalBatch,
                    combine=lambda results: _ProposalBatch(
                        proposals=[results[f"proposer_{i}"] for i in range(len(self.proposers))]  # type: ignore[list-item]
                    ),
                )
                workflow = Sequential(
                    _InitDebateRecord(proposer_fanout=proposer_fanout),
                    _CritiqueRounds(
                        critic=self.critic,
                        rounds=self.rounds,
                        algorithm_path=path,
                    ),
                    self.synthesizer,
                    input=DebateContext,
                    output=Answer,
                )

                result = await _run_sequential(workflow, x)
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={"rounds": self.rounds},
                    started_at=started,
                    finished_at=time.time(),
                )
                return result  # type: ignore[return-value]
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
