"""Tests for `operad.Debate`."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.algorithms import (
    Critique,
    Debate,
    DebateRecord,
    DebateTurn,
    Proposal,
)

from ..conftest import A, B


pytestmark = pytest.mark.asyncio


class _Proposer(Agent[A, Proposal]):
    input = A
    output = Proposal

    def __init__(self, cfg, author: str) -> None:
        super().__init__(config=cfg, input=A, output=Proposal)
        self.author = author

    async def forward(self, x: A) -> Proposal:  # type: ignore[override]
        return Proposal(
            content=f"{self.author}:{x.text}",
            author=self.author,
        )


class _Critic(Agent[DebateTurn, Critique]):
    input = DebateTurn
    output = Critique

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=DebateTurn, output=Critique)
        self.turns: list[DebateTurn] = []

    async def forward(self, x: DebateTurn) -> Critique:  # type: ignore[override]
        self.turns.append(x)
        author = x.focus.author if x.focus is not None else ""
        return Critique(target_author=author, comments="ok", score=1.0)


class _Synth(Agent[DebateRecord, B]):
    input = DebateRecord
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=DebateRecord, output=B)
        self.seen: DebateRecord | None = None

    async def forward(self, x: DebateRecord) -> B:  # type: ignore[override]
        self.seen = x
        return B.model_construct(value=len(x.proposals) + len(x.critiques))


async def test_debate_runs_all_proposers(cfg) -> None:
    p1 = await _Proposer(cfg, "alice").abuild()
    p2 = await _Proposer(cfg, "bob").abuild()
    p3 = await _Proposer(cfg, "carol").abuild()
    critic = await _Critic(cfg).abuild()
    synth = await _Synth(cfg).abuild()

    debate = Debate([p1, p2, p3], critic, synth, rounds=0)
    out = await debate.run(A(text="q"))
    assert out.value == 3  # 3 proposals, 0 critiques
    assert synth.seen is not None
    authors = {p.author for p in synth.seen.proposals}
    assert authors == {"alice", "bob", "carol"}


async def test_debate_accumulates_critiques_across_rounds(cfg) -> None:
    p1 = await _Proposer(cfg, "alice").abuild()
    p2 = await _Proposer(cfg, "bob").abuild()
    critic = await _Critic(cfg).abuild()
    synth = await _Synth(cfg).abuild()
    critic.turns.clear()

    debate = Debate([p1, p2], critic, synth, rounds=2)
    out = await debate.run(A(text="q"))
    # 2 proposals + (2 proposals * 2 rounds) = 6
    assert out.value == 6
    assert len(critic.turns) == 4
    assert synth.seen is not None and len(synth.seen.critiques) == 4


async def test_debate_rejects_empty_proposers(cfg) -> None:
    critic = _Critic(cfg)
    synth = _Synth(cfg)
    with pytest.raises(ValueError, match="proposers"):
        Debate([], critic, synth, rounds=1)


async def test_debate_rejects_negative_rounds(cfg) -> None:
    p1 = _Proposer(cfg, "alice")
    critic = _Critic(cfg)
    synth = _Synth(cfg)
    with pytest.raises(ValueError, match="rounds"):
        Debate([p1], critic, synth, rounds=-1)
