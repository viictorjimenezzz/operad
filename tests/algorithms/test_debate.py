"""Tests for `operad.Debate`."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.agents.debate.schemas import (
    Critique,
    DebateContext,
    DebateRecord,
    DebateTurn,
    Proposal,
)
from operad.agents.reasoning.schemas import Answer
from operad.algorithms import Debate


pytestmark = pytest.mark.asyncio


class _Proposer(Agent[DebateContext, Proposal]):
    input = DebateContext
    output = Proposal

    def __init__(self, cfg, author: str) -> None:
        super().__init__(config=cfg, input=DebateContext, output=Proposal)
        self.author = author

    async def forward(self, x: DebateContext) -> Proposal:  # type: ignore[override]
        topic = getattr(x, "topic", "")
        return Proposal(
            content=f"{self.author}:{topic}",
            author=self.author,
        )


_SHARED_TURNS: list[DebateTurn] = []


class _Critic(Agent[DebateTurn, Critique]):
    input = DebateTurn
    output = Critique

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=DebateTurn, output=Critique)

    async def forward(self, x: DebateTurn) -> Critique:  # type: ignore[override]
        _SHARED_TURNS.append(x)
        author = x.focus.author if x.focus is not None else ""
        return Critique(target_author=author, comments="ok", score=1.0)


class _Synth(Agent[DebateRecord, Answer]):
    input = DebateRecord
    output = Answer

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=DebateRecord, output=Answer)
        self.seen: DebateRecord | None = None

    async def forward(self, x: DebateRecord) -> Answer:  # type: ignore[override]
        self.seen = x
        return Answer(
            reasoning=f"{len(x.proposals)} proposals / {len(x.critiques)} critiques",
            answer=str(len(x.proposals) + len(x.critiques)),
        )


async def _make_debate(cfg, *, proposer_authors: list[str], **kwargs) -> Debate:
    """Construct a Debate with scripted proposers / critic / synthesizer."""
    debate = Debate(**kwargs)
    debate.proposers = [
        await _Proposer(cfg, a).abuild() for a in proposer_authors
    ]
    debate.critic = await _Critic(cfg).abuild()
    debate.synthesizer = await _Synth(cfg).abuild()
    _SHARED_TURNS.clear()
    return debate


async def test_debate_runs_all_proposers(cfg) -> None:
    debate = await _make_debate(
        cfg, proposer_authors=["alice", "bob", "carol"], rounds=0
    )
    out = await debate.run(DebateContext(topic="q"))
    assert out.answer == "3"  # 3 proposals + 0 critiques
    assert debate.synthesizer.seen is not None
    authors = {p.author for p in debate.synthesizer.seen.proposals}
    assert authors == {"alice", "bob", "carol"}


async def test_debate_accumulates_critiques_across_rounds(cfg) -> None:
    debate = await _make_debate(
        cfg, proposer_authors=["alice", "bob"], rounds=2
    )
    out = await debate.run(DebateContext(topic="q"))
    # 2 proposals + (2 proposals * 2 rounds) = 6
    assert out.answer == "6"
    # 2 proposals critiqued per round, across 2 rounds.
    actual_turns = [t for t in _SHARED_TURNS if t.record is not None]
    assert len(actual_turns) == 4
    assert debate.synthesizer.seen is not None
    assert len(debate.synthesizer.seen.critiques) == 4


async def test_debate_rejects_empty_proposers() -> None:
    class _EmptyDebate(Debate):
        proposers = []  # type: ignore[assignment]

    with pytest.raises(ValueError, match="proposers"):
        _EmptyDebate()


async def test_debate_rejects_negative_rounds() -> None:
    with pytest.raises(ValueError, match="rounds"):
        Debate(rounds=-1)


async def test_debate_propagates_context_to_components() -> None:
    debate = Debate(context="civic policy debate")
    assert debate.critic.context == "civic policy debate"
    assert debate.synthesizer.context == "civic policy debate"
    for p in debate.proposers:
        assert p.context == "civic policy debate"
