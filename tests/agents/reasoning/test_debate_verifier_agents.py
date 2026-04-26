"""Tests for DebateAgent and VerifierAgent pre-wired wrappers."""

from __future__ import annotations

import pytest

from operad import Agent
from operad.agents import DebateAgent, VerifierAgent
from operad.agents.debate.schemas import (
    Critique,
    DebateContext,
    DebateRecord,
    DebateTurn,
    Proposal,
)
from operad.agents.reasoning.schemas import Answer, Candidate, Score, Task
from operad.agents import Sequential
from operad.runtime.observers import AlgorithmEvent, registry
from tests.conftest import A, B, FakeLeaf


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Scripted stand-ins (no LLM)
# ---------------------------------------------------------------------------


class _Proposer(Agent[DebateContext, Proposal]):
    input = DebateContext
    output = Proposal

    def __init__(self, cfg, name: str = "p") -> None:
        super().__init__(config=cfg, input=DebateContext, output=Proposal)
        self._name = name

    async def forward(self, x: DebateContext) -> Proposal:  # type: ignore[override]
        return Proposal(content=f"{self._name}:{x.topic}", author=self._name)


class _DebateCritic(Agent[DebateTurn, Critique]):
    input = DebateTurn
    output = Critique

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=DebateTurn, output=Critique)

    async def forward(self, x: DebateTurn) -> Critique:  # type: ignore[override]
        author = x.focus.author if x.focus is not None else ""
        return Critique(target_author=author, comments="ok", score=1.0)


class _Synth(Agent[DebateRecord, Answer]):
    input = DebateRecord
    output = Answer

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=DebateRecord, output=Answer)

    async def forward(self, x: DebateRecord) -> Answer:  # type: ignore[override]
        return Answer(reasoning="synthesized", answer="final")


class _Generator(Agent[Task, Answer]):
    input = Task
    output = Answer

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=Task, output=Answer)
        self.calls = 0

    async def forward(self, x: Task) -> Answer:  # type: ignore[override]
        self.calls += 1
        return Answer(reasoning="gen", answer=f"attempt-{self.calls}")


class _Critic(Agent[Candidate, Score]):
    input = Candidate
    output = Score

    def __init__(self, cfg, *, pass_on_call: int = 1) -> None:
        super().__init__(config=cfg, input=Candidate, output=Score)
        self._pass_on_call = pass_on_call
        self._calls = 0

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        self._calls += 1
        score = 1.0 if self._calls >= self._pass_on_call else 0.0
        return Score(score=score, rationale="ok")


# ---------------------------------------------------------------------------
# DebateAgent — typed I/O
# ---------------------------------------------------------------------------


async def test_debate_agent_returns_answer(cfg) -> None:
    agent = DebateAgent(
        proposers=[_Proposer(cfg, "a"), _Proposer(cfg, "b")],
        critic=_DebateCritic(cfg),
        synthesizer=_Synth(cfg),
        rounds=0,
    )
    await agent.abuild()
    result = await agent(DebateContext(topic="best lang"))
    assert isinstance(result.response, Answer)
    assert result.response.answer == "final"


async def test_debate_agent_children_registered(cfg) -> None:
    agent = DebateAgent(
        proposers=[_Proposer(cfg, "x"), _Proposer(cfg, "y")],
        critic=_DebateCritic(cfg),
        synthesizer=_Synth(cfg),
    )
    assert "proposer_0" in agent._children
    assert "proposer_1" in agent._children
    assert "debate_critic" in agent._children
    assert "synthesizer" in agent._children


# ---------------------------------------------------------------------------
# VerifierAgent — typed I/O
# ---------------------------------------------------------------------------


async def test_verifier_agent_returns_answer(cfg) -> None:
    gen = _Generator(cfg)
    crit = _Critic(cfg, pass_on_call=1)
    agent = VerifierAgent(generator=gen, verifier=crit, threshold=0.9, max_iter=3)
    await agent.abuild()
    result = await agent(Task(goal="solve it"))
    assert isinstance(result.response, Answer)
    assert result.response.answer == "attempt-1"


async def test_verifier_agent_iterates_until_threshold(cfg) -> None:
    gen = _Generator(cfg)
    crit = _Critic(cfg, pass_on_call=2)  # fails first call, passes second
    agent = VerifierAgent(generator=gen, verifier=crit, threshold=0.9, max_iter=3)
    await agent.abuild()
    result = await agent(Task(goal="hard problem"))
    assert result.response.answer == "attempt-2"
    assert gen.calls == 2


async def test_verifier_agent_children_registered(cfg) -> None:
    agent = VerifierAgent(config=None)
    assert "generator" in agent._children
    assert "verifier" in agent._children


# ---------------------------------------------------------------------------
# Sequential composition
# ---------------------------------------------------------------------------


async def test_debate_agent_in_pipeline(cfg) -> None:
    """Sequential(leaf -> DebateAgent -> leaf) builds and runs end-to-end."""
    pre = FakeLeaf(config=cfg, input=A, output=DebateContext, canned={"topic": "test", "details": ""})
    debate = DebateAgent(
        proposers=[_Proposer(cfg, "p1")],
        critic=_DebateCritic(cfg),
        synthesizer=_Synth(cfg),
        rounds=0,
    )
    post = FakeLeaf(config=cfg, input=Answer, output=B, canned={"value": 42})

    pipeline = Sequential(pre, debate, post, input=A, output=B)
    await pipeline.abuild()

    result = await pipeline(A(text="go"))
    assert isinstance(result.response, B)
    assert result.response.value == 42


async def test_verifier_agent_in_pipeline(cfg) -> None:
    """Sequential(leaf -> VerifierAgent -> leaf) builds and runs end-to-end."""
    pre = FakeLeaf(config=cfg, input=A, output=Task, canned={"goal": "test"})
    verifier = VerifierAgent(
        generator=_Generator(cfg),
        verifier=_Critic(cfg, pass_on_call=1),
        threshold=0.9,
        max_iter=2,
    )
    post = FakeLeaf(config=cfg, input=Answer, output=B, canned={"value": 7})

    pipeline = Sequential(pre, verifier, post, input=A, output=B)
    await pipeline.abuild()

    result = await pipeline(A(text="start"))
    assert isinstance(result.response, B)
    assert result.response.value == 7


# ---------------------------------------------------------------------------
# Event forwarding
# ---------------------------------------------------------------------------


class _AlgoEventCapture:
    def __init__(self) -> None:
        self.events: list[AlgorithmEvent] = []

    async def on_event(self, event) -> None:
        if isinstance(event, AlgorithmEvent):
            self.events.append(event)


async def test_debate_agent_emits_algo_events(cfg) -> None:
    capture = _AlgoEventCapture()
    registry.register(capture)
    try:
        agent = DebateAgent(
            proposers=[_Proposer(cfg, "a")],
            critic=_DebateCritic(cfg),
            synthesizer=_Synth(cfg),
            rounds=1,
        )
        await agent.abuild()
        await agent(DebateContext(topic="events?"))
    finally:
        registry.unregister(capture)

    kinds = {e.kind for e in capture.events}
    assert "algo_start" in kinds
    assert "algo_end" in kinds


async def test_verifier_agent_emits_algo_events(cfg) -> None:
    capture = _AlgoEventCapture()
    registry.register(capture)
    try:
        agent = VerifierAgent(
            generator=_Generator(cfg),
            verifier=_Critic(cfg, pass_on_call=1),
            threshold=0.9,
            max_iter=2,
        )
        await agent.abuild()
        await agent(Task(goal="emit events"))
    finally:
        registry.unregister(capture)

    kinds = {e.kind for e in capture.events}
    assert "algo_start" in kinds
    assert "algo_end" in kinds
