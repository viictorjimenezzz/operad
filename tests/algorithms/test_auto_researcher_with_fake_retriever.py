"""End-to-end: `AutoResearcher` swaps in a `FakeRetriever` for offline runs."""

from __future__ import annotations

import pytest

from operad import Configuration
from operad.agents.reasoning.components import (
    Critic,
    FakeRetriever,
    Planner,
    Reasoner,
    Reflector,
)
from operad.agents.reasoning.schemas import (
    Answer,
    Candidate,
    Hit,
    Reflection,
    ReflectionInput,
    Score,
    Task,
)
from operad.algorithms import AutoResearcher, ResearchInput, ResearchPlan


pytestmark = pytest.mark.asyncio


class _Planner(Planner):
    input = Task
    output = ResearchPlan

    def __init__(self, cfg: Configuration) -> None:
        super().__init__(config=cfg, input=Task, output=ResearchPlan)

    async def forward(self, x: Task) -> ResearchPlan:  # type: ignore[override]
        return ResearchPlan(query="capital of France")


class _Reasoner(Reasoner):
    input = ResearchInput
    output = Answer

    def __init__(self, cfg: Configuration) -> None:
        super().__init__(config=cfg, input=ResearchInput, output=Answer)
        self.last_hits: list[str] = []

    async def forward(self, x: ResearchInput) -> Answer:  # type: ignore[override]
        hits = getattr(x, "hits", None)
        items = list(hits.items) if hits is not None else []
        self.last_hits = [h.text for h in items]
        top = self.last_hits[0] if self.last_hits else ""
        return Answer(reasoning=f"saw {len(self.last_hits)} hits", answer=top)


class _Critic(Critic):
    def __init__(self, cfg: Configuration) -> None:
        super().__init__(config=cfg, input=Candidate, output=Score)

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        return Score(score=1.0, rationale="ok")


class _Reflector(Reflector):
    def __init__(self, cfg: Configuration) -> None:
        super().__init__(config=cfg, input=ReflectionInput, output=Reflection)

    async def forward(self, x: ReflectionInput) -> Reflection:  # type: ignore[override]
        return Reflection(needs_revision=False, suggested_revision="")


async def test_auto_researcher_runs_with_fake_retriever(cfg) -> None:
    corpus = [
        Hit(text="Paris is the capital of France.", score=0.0, source="wiki"),
        Hit(text="Bananas are yellow.", score=0.0, source="trivia"),
    ]
    retriever = await FakeRetriever(corpus=corpus, scorer="jaccard").abuild()
    planner = await _Planner(cfg).abuild()
    reasoner = await _Reasoner(cfg).abuild()
    critic = await _Critic(cfg).abuild()
    reflector = await _Reflector(cfg).abuild()

    ar = AutoResearcher(n=1, max_iter=0)
    ar.planner = planner
    ar.retriever = retriever
    ar.reasoner = reasoner
    ar.critic = critic
    ar.reflector = reflector
    out = await ar.run(Task(goal="What is the capital of France?"))

    assert isinstance(out, Answer)
    assert out.answer == "Paris is the capital of France."
    assert reasoner.last_hits[0] == "Paris is the capital of France."
