"""Integration tests: every algorithm emits AlgorithmEvents at boundaries.

For each algorithm we attach a `MemObs`-style collector to the registry,
run a small offline scenario, and assert the event sequence.
"""

from __future__ import annotations

import random

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.agents import Reflection, ReflectionInput
from operad.agents.reasoning.components import (
    Critic,
    Planner,
    Reasoner,
    Reflector,
    Retriever,
)
from operad.agents.reasoning.schemas import Answer, Hit, Query, Task
from operad.algorithms import (
    AutoResearcher,
    BestOfN,
    Candidate,
    Critique,
    Debate,
    DebateRecord,
    DebateTurn,
    Evolutionary,
    Proposal,
    RefinementInput,
    ResearchInput,
    ResearchPlan,
    Score,
    SelfRefine,
    Sweep,
    VerifierLoop,
)
from operad.metrics.base import MetricBase
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import AgentEvent, Event
from operad.runtime.observers import registry as obs_registry
from operad.utils.ops import AppendRule

from ..conftest import A, B


pytestmark = pytest.mark.asyncio


class _Collector:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def on_event(self, event: Event) -> None:
        self.events.append(event)


@pytest.fixture
def col():
    obs_registry.clear()
    c = _Collector()
    obs_registry.register(c)
    yield c
    obs_registry.clear()


def _algo_events(events: list[Event]) -> list[AlgorithmEvent]:
    return [e for e in events if isinstance(e, AlgorithmEvent)]


def _algo_kinds(events: list[Event]) -> list[str]:
    return [e.kind for e in _algo_events(events)]


# ----- best_of_n --------------------------------------------------------


class _Counter(Agent[A, B]):
    input = A
    output = B

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=A, output=B)
        self.calls = 0

    async def forward(self, x: A) -> B:  # type: ignore[override]
        self.calls += 1
        return B.model_construct(value=self.calls * 10)


class _ScoreByCandidate(Agent[Candidate, Score]):
    input = Candidate
    output = Score

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        value = getattr(x.output, "value", 0) if x.output is not None else 0
        return Score(score=float(value), rationale="")


async def test_best_of_n_emits_candidate_events(cfg, col) -> None:
    gen = await _Counter(cfg).abuild()
    judge = await _ScoreByCandidate(config=cfg).abuild()
    gen.calls = 0

    bon = BestOfN(generator=gen, judge=judge, n=3)
    await bon.run(A(text="go"))

    kinds = _algo_kinds(col.events)
    assert kinds == ["algo_start", "candidate", "candidate", "candidate", "algo_end"]
    algo = _algo_events(col.events)
    assert all(e.algorithm_path == "BestOfN" for e in algo)
    candidates = [e for e in algo if e.kind == "candidate"]
    assert [e.payload["candidate_index"] for e in candidates] == [0, 1, 2]
    assert "best_index" in algo[-1].payload
    assert "score" in algo[-1].payload


async def test_run_id_shared_with_agent_events(cfg, col) -> None:
    gen = await _Counter(cfg).abuild()
    judge = await _ScoreByCandidate(config=cfg).abuild()
    gen.calls = 0

    bon = BestOfN(generator=gen, judge=judge, n=2)
    await bon.run(A(text="go"))

    algo_ids = {e.run_id for e in col.events if isinstance(e, AlgorithmEvent)}
    leaf_ids = {e.run_id for e in col.events if isinstance(e, AgentEvent)}
    assert len(algo_ids) == 1
    assert algo_ids == leaf_ids


# ----- evolutionary -----------------------------------------------------


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    value: int = 0


class _RuleCountLeaf(Agent[Q, R]):
    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        return R.model_construct(value=len(self.rules))


class _RuleCountMetric(MetricBase):
    name = "rule_count"

    def __init__(self, target: int) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


async def test_evolutionary_emits_one_event_per_generation(cfg, col) -> None:
    seed = _RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    evo = Evolutionary(
        seed=seed,
        mutations=[AppendRule(path="", rule="x")],
        metric=_RuleCountMetric(target=3),
        dataset=[(Q(text="a"), R(value=3))],
        population_size=4,
        generations=2,
        rng=random.Random(0),
    )
    await evo.run()

    kinds = _algo_kinds(col.events)
    assert kinds == ["algo_start", "generation", "generation", "algo_end"]
    gens = [e for e in _algo_events(col.events) if e.kind == "generation"]
    assert [e.payload["gen_index"] for e in gens] == [0, 1]
    for g in gens:
        assert len(g.payload["population_scores"]) == 4
        assert len(g.payload["survivor_indices"]) == 2  # half of 4


# ----- debate -----------------------------------------------------------


class _Proposer(Agent[A, Proposal]):
    input = A
    output = Proposal

    def __init__(self, cfg, author: str) -> None:
        super().__init__(config=cfg, input=A, output=Proposal)
        self.author = author

    async def forward(self, x: A) -> Proposal:  # type: ignore[override]
        return Proposal(content=f"{self.author}:{x.text}", author=self.author)


class _DebateCritic(Agent[DebateTurn, Critique]):
    input = DebateTurn
    output = Critique

    async def forward(self, x: DebateTurn) -> Critique:  # type: ignore[override]
        author = x.focus.author if x.focus is not None else ""
        return Critique(target_author=author, comments="ok", score=0.7)


class _Synth(Agent[DebateRecord, B]):
    input = DebateRecord
    output = B

    async def forward(self, x: DebateRecord) -> B:  # type: ignore[override]
        return B.model_construct(value=len(x.proposals))


async def test_debate_emits_round_with_lists(cfg, col) -> None:
    p1 = await _Proposer(cfg, "alice").abuild()
    p2 = await _Proposer(cfg, "bob").abuild()
    critic = await _DebateCritic(config=cfg).abuild()
    synth = await _Synth(config=cfg).abuild()

    debate = Debate([p1, p2], critic, synth, rounds=2)
    await debate.run(A(text="q"))

    kinds = _algo_kinds(col.events)
    assert kinds == ["algo_start", "round", "round", "algo_end"]
    rounds = [e for e in _algo_events(col.events) if e.kind == "round"]
    assert [r.payload["round_index"] for r in rounds] == [0, 1]
    for r in rounds:
        assert len(r.payload["proposals"]) == 2
        assert len(r.payload["critiques"]) == 2
        assert r.payload["scores"] == [0.7, 0.7]


# ----- sweep ------------------------------------------------------------


class _EchoTask(Agent[A, B]):
    input = A
    output = B

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return B.model_construct(value=len(self.task))


async def test_sweep_emits_one_event_per_cell(cfg, col) -> None:
    seed = _EchoTask(config=cfg, task="x")
    await seed.abuild()

    sweep = Sweep(seed, {"task": ["a", "bb"], "role": ["r1", "r2"]})
    await sweep.run(A(text="go"))

    kinds = _algo_kinds(col.events)
    assert kinds[0] == "algo_start"
    assert kinds[-1] == "algo_end"
    cells = [e for e in _algo_events(col.events) if e.kind == "cell"]
    assert len(cells) == 4
    assert [c.payload["cell_index"] for c in cells] == [0, 1, 2, 3]
    # score is a None placeholder; SweepCell has no native score.
    assert all(c.payload["score"] is None for c in cells)


# ----- self_refine ------------------------------------------------------


class _Gen(Agent[A, B]):
    input = A
    output = B

    async def forward(self, x: A) -> B:  # type: ignore[override]
        return B.model_construct(value=1)


class _ScriptedReflector(Agent[ReflectionInput, Reflection]):
    input = ReflectionInput
    output = Reflection

    def __init__(self, cfg, scripted: list[bool]) -> None:
        super().__init__(config=cfg, input=ReflectionInput, output=Reflection)
        self.scripted = list(scripted)
        self.calls = 0

    async def forward(self, x: ReflectionInput) -> Reflection:  # type: ignore[override]
        i = min(self.calls, len(self.scripted) - 1)
        needs = self.scripted[i]
        self.calls += 1
        return Reflection(needs_revision=needs)


class _Refiner(Agent[RefinementInput, B]):
    input = RefinementInput
    output = B

    async def forward(self, x: RefinementInput) -> B:  # type: ignore[override]
        prior_val = getattr(x.prior, "value", 0)
        return B.model_construct(value=prior_val + 1)


async def test_self_refine_emits_iteration_events(cfg, col) -> None:
    gen = await _Gen(config=cfg).abuild()
    reflector = await _ScriptedReflector(cfg, scripted=[True, False]).abuild()
    refiner = await _Refiner(config=cfg).abuild()
    reflector.calls = 0

    loop = SelfRefine(gen, reflector, refiner, max_iter=3)
    await loop.run(A(text="q"))

    kinds = _algo_kinds(col.events)
    # iter 0 reflect (needs revision), iter 0 refine, iter 1 reflect (done)
    assert kinds == ["algo_start", "iteration", "iteration", "iteration", "algo_end"]
    iters = [e for e in _algo_events(col.events) if e.kind == "iteration"]
    assert [(i.payload["iter_index"], i.payload["phase"]) for i in iters] == [
        (0, "reflect"),
        (0, "refine"),
        (1, "reflect"),
    ]


# ----- verifier_loop ----------------------------------------------------


class _ThresholdCritic(Agent[Candidate, Score]):
    input = Candidate
    output = Score

    def __init__(self, cfg, threshold: int) -> None:
        super().__init__(config=cfg, input=Candidate, output=Score)
        self.threshold = threshold

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        value = getattr(x.output, "value", 0) if x.output is not None else 0
        return Score(score=1.0 if value >= self.threshold else 0.0)


async def test_verifier_loop_emits_iteration_with_score(cfg, col) -> None:
    gen = await _Counter(cfg).abuild()
    critic = await _ThresholdCritic(cfg, threshold=20).abuild()
    gen.calls = 0

    loop = VerifierLoop(gen, critic, threshold=0.8, max_iter=5)
    await loop.run(A(text="q"))

    kinds = _algo_kinds(col.events)
    # First iter score=0.0 (value=10); second clears threshold (value=20).
    assert kinds == ["algo_start", "iteration", "iteration", "algo_end"]
    iters = [e for e in _algo_events(col.events) if e.kind == "iteration"]
    assert [i.payload["score"] for i in iters] == [0.0, 1.0]
    assert all(i.payload["phase"] == "verify" for i in iters)


# ----- auto_research ----------------------------------------------------


class _ARPlanner(Planner):
    input = Task
    output = ResearchPlan

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=Task, output=ResearchPlan)

    async def forward(self, x: Task) -> ResearchPlan:  # type: ignore[override]
        return ResearchPlan(query="q")


class _ARReasoner(Reasoner):
    input = ResearchInput
    output = Answer

    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=ResearchInput, output=Answer)

    async def forward(self, x: ResearchInput) -> Answer:  # type: ignore[override]
        return Answer(reasoning="r", answer="a")


class _ARCritic(Critic):
    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=Candidate, output=Score)

    async def forward(self, x: Candidate) -> Score:  # type: ignore[override]
        return Score(score=1.0, rationale="")


class _ARReflector(Reflector):
    def __init__(self, cfg) -> None:
        super().__init__(config=cfg, input=ReflectionInput, output=Reflection)

    async def forward(self, x: ReflectionInput) -> Reflection:  # type: ignore[override]
        return Reflection(needs_revision=True)


async def test_auto_researcher_emits_iteration_events(cfg, col) -> None:
    planner = await _ARPlanner(cfg).abuild()

    async def lookup(q: Query) -> list[Hit]:
        return [Hit(text="hit", score=1.0)]

    retriever = await Retriever(lookup=lookup).abuild()
    reasoner = await _ARReasoner(cfg).abuild()
    critic = await _ARCritic(cfg).abuild()
    reflector = await _ARReflector(cfg).abuild()

    ar = AutoResearcher(
        planner=planner,
        retriever=retriever,
        reasoner=reasoner,
        critic=critic,
        reflector=reflector,
        n=2,
        max_iter=0,
    )
    await ar.run(Task(goal="go"))

    algo = _algo_events(col.events)
    kinds = [e.kind for e in algo]
    # algo_start + 1 iteration per attempt (n=2, no inner loop) + algo_end
    assert kinds.count("algo_start") == 1
    assert kinds.count("algo_end") == 1
    iters = [e for e in algo if e.kind == "iteration"]
    assert len(iters) == 2
    assert all(i.payload["phase"] == "reason" for i in iters)


# ----- error path -------------------------------------------------------


async def test_algorithm_emits_algo_error_on_exception(cfg, col) -> None:
    gen = await _Counter(cfg).abuild()
    judge = await _ScoreByCandidate(config=cfg).abuild()

    async def boom(x: A) -> B:
        raise RuntimeError("boom")

    gen.forward = boom  # type: ignore[method-assign]

    bon = BestOfN(generator=gen, judge=judge, n=1)
    with pytest.raises(RuntimeError, match="boom"):
        await bon.run(A(text="go"))

    algo = _algo_events(col.events)
    assert algo[0].kind == "algo_start"
    assert algo[-1].kind == "algo_error"
    assert algo[-1].payload["type"] == "RuntimeError"
    assert algo[-1].payload["message"] == "boom"
