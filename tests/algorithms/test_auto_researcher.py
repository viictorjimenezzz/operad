"""Tests for `operad.algorithms.AutoResearcher`."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad import Agent, Configuration
from operad.agents.reasoning.components import (
    Critic,
    Planner,
    Reasoner,
    Reflector,
    Retriever,
)
from operad.agents.reasoning.schemas import (
    Answer,
    Candidate,
    Hit,
    Query,
    Reflection,
    ReflectionInput,
    Score,
)
from operad.algorithms import (
    AutoResearcher,
    ResearchContext,
    ResearchInput,
    ResearchPlan,
)


pytestmark = pytest.mark.asyncio


class _Planner(Planner):
    input = ResearchContext
    output = ResearchPlan

    def __init__(self, cfg: Configuration) -> None:
        super().__init__(config=cfg, input=ResearchContext, output=ResearchPlan)
        self.calls = 0

    async def forward(self, x: ResearchContext) -> ResearchPlan:  # type: ignore[override]
        self.calls += 1
        return ResearchPlan(query=f"q-{self.calls}")


class _Reasoner(Reasoner):
    input = ResearchInput
    output = Answer

    def __init__(self, cfg: Configuration) -> None:
        super().__init__(config=cfg, input=ResearchInput, output=Answer)
        self.calls = 0

    async def forward(self, x: ResearchInput) -> Answer:  # type: ignore[override]
        self.calls += 1
        return Answer(reasoning=f"r-{self.calls}", answer=f"a-{self.calls}")


class _ScriptedCritic(Critic):
    def __init__(self, cfg: Configuration, scores: list[float]) -> None:
        super().__init__(config=cfg, input=Candidate, output=Score)
        self._scores = list(scores)
        self.calls = 0

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        i = self.calls
        s = self._scores[i] if i < len(self._scores) else self._scores[-1]
        self.calls += 1
        return Score(score=s, rationale=f"s={s}")


class _Reflector(Reflector):
    def __init__(self, cfg: Configuration) -> None:
        super().__init__(config=cfg, input=ReflectionInput, output=Reflection)
        self.calls = 0

    async def forward(self, x: ReflectionInput) -> Reflection:  # type: ignore[override]
        self.calls += 1
        return Reflection(
            score=0.2,
            needs_revision=True,
            suggested_revision=f"rev-{self.calls}",
        )


def _make_retriever() -> tuple[Retriever, list[Query]]:
    seen: list[Query] = []

    async def lookup(q: Query) -> list[Hit]:
        seen.append(q)
        return [Hit(text="hit", score=1.0)]

    return Retriever(lookup=lookup), seen


async def _make_ar(
    cfg: Configuration,
    *,
    scores: list[float] | None = None,
    **kwargs,
) -> tuple[AutoResearcher, list[Query]]:
    """Construct an AutoResearcher and swap each component for a scripted fake."""
    planner = await _Planner(cfg).abuild()
    retriever, seen = _make_retriever()
    retriever = await retriever.abuild()
    reasoner = await _Reasoner(cfg).abuild()
    critic = await _ScriptedCritic(cfg, scores or [1.0] * 64).abuild()
    reflector = await _Reflector(cfg).abuild()
    for a in (planner, reasoner, critic, reflector):
        a.calls = 0  # reset post-trace
    seen.clear()

    ar = AutoResearcher(**kwargs)
    ar.planner = planner
    ar.retriever = retriever
    ar.reasoner = reasoner
    ar.critic = critic
    ar.reflector = reflector
    return ar, seen


async def test_auto_researcher_runs_end_to_end(cfg) -> None:
    ar, _ = await _make_ar(cfg, n=1, max_iter=0)
    out = await ar.run(ResearchContext(goal="what is TCP?"))
    assert isinstance(out, Answer)
    assert out.answer.startswith("a-")


async def test_auto_researcher_produces_n_candidates(cfg) -> None:
    ar, seen = await _make_ar(cfg, n=4, max_iter=0)
    await ar.run(ResearchContext(goal="go"))
    assert ar.planner.calls == 4
    assert len(seen) == 4
    assert ar.reasoner.calls == 4
    assert ar.critic.calls == 4
    assert ar.reflector.calls == 0


async def test_auto_researcher_picks_highest_scoring(cfg) -> None:
    ar, _ = await _make_ar(
        cfg, scores=[0.1, 0.9, 0.2], n=3, max_iter=0, threshold=0.0
    )
    out = await ar.run(ResearchContext(goal="go"))
    assert isinstance(out, Answer)
    # Reasoner emits a-1, a-2, a-3 across the three attempts (in gather
    # order). Critic assigns 0.1, 0.9, 0.2 respectively; a-2 wins.
    assert out.answer == "a-2"


async def test_auto_researcher_max_iter_zero_skips_reflection(cfg) -> None:
    ar, _ = await _make_ar(
        cfg, scores=[0.0], n=2, max_iter=0, threshold=0.99,
    )
    await ar.run(ResearchContext(goal="go"))
    assert ar.reflector.calls == 0
    assert ar.reasoner.calls == 2  # one per attempt, no revisions


async def test_auto_researcher_loops_when_score_below_threshold(cfg) -> None:
    # First score below threshold forces one reflect pass; second score
    # clears the threshold and the loop exits early.
    ar, _ = await _make_ar(
        cfg, scores=[0.1, 0.95], n=1, max_iter=3, threshold=0.9,
    )
    await ar.run(ResearchContext(goal="go"))
    assert ar.reasoner.calls == 2
    assert ar.reflector.calls == 1
    assert ar.critic.calls == 2


async def test_auto_researcher_rejects_zero_n() -> None:
    with pytest.raises(ValueError, match="n must be >= 1"):
        AutoResearcher(n=0)


async def test_auto_researcher_rejects_negative_max_iter() -> None:
    with pytest.raises(ValueError, match="max_iter must be >= 0"):
        AutoResearcher(max_iter=-1)


async def test_auto_researcher_is_not_an_agent() -> None:
    ar = AutoResearcher()
    assert not isinstance(ar, Agent)


async def test_auto_researcher_importable() -> None:
    from operad.algorithms import (
        AutoResearcher as _AR,
        ResearchInput as _RI,
        ResearchPlan as _RP,
    )

    assert _AR is AutoResearcher
    assert issubclass(_RI, BaseModel)
    assert issubclass(_RP, BaseModel)


async def test_auto_researcher_not_promoted_to_operad_top_level() -> None:
    import operad

    assert "AutoResearcher" not in getattr(operad, "__all__", ())


async def test_research_context_is_algorithm_input() -> None:
    ctx = ResearchContext(
        goal="Summarize the REPowerEU plan.",
        domain="climate science",
        audience="policy researchers",
        constraints="no paywalled sources",
        notes="focus on EU",
    )
    assert ctx.goal == "Summarize the REPowerEU plan."
