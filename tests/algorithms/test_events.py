"""Integration tests: every algorithm emits AlgorithmEvents at boundaries.

For each algorithm we attach a `MemObs`-style collector to the
registry, run a small offline scenario, and assert the event
sequence.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.agents import Reflection, ReflectionInput
from operad.agents.debate.schemas import (
    Critique,
    DebateContext,
    DebateRecord,
    DebateTurn,
    Proposal,
)
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
    Score,
    Task,
)
from operad.algorithms import (
    AutoResearcher,
    Beam,
    Debate,
    MutationBeam,
    ResearchInput,
    ResearchPlan,
    Sweep,
    VerifierLoop,
)
from operad.algorithms.mutation_beam import (
    MutationJudgeCandidate,
    MutationJudgeInput,
    MutationProposal,
    MutationProposalBatch,
    MutationProposalInput,
)
from operad.metrics.base import MetricBase
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers import AgentEvent, Event
from operad.runtime.observers import registry as obs_registry

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


# ----- beam -------------------------------------------------------------


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


async def _make_beam(cfg, **kwargs) -> Beam:
    beam = Beam(**kwargs)
    beam.generator = await _Counter(cfg).abuild()
    beam.generator.calls = 0
    beam.judge = await _ScoreByCandidate(config=cfg).abuild()
    return beam


async def test_beam_emits_candidate_events(cfg, col) -> None:
    beam = await _make_beam(cfg, n=3)
    await beam.run(A(text="go"))

    kinds = _algo_kinds(col.events)
    assert kinds == ["algo_start", "candidate", "candidate", "candidate", "iteration", "algo_end"]
    algo = _algo_events(col.events)
    assert all(e.algorithm_path == "Beam" for e in algo)
    candidates = [e for e in algo if e.kind == "candidate"]
    assert [e.payload["candidate_index"] for e in candidates] == [0, 1, 2]
    assert "top_indices" in algo[-1].payload
    assert "top_scores" in algo[-1].payload


async def test_beam_without_judge_emits_truncate_phase(cfg, col) -> None:
    beam: Beam = Beam(n=3, top_k=2)
    beam.generator = await _Counter(cfg).abuild()
    beam.generator.calls = 0
    beam.judge = None
    await beam.run(A(text="go"))

    kinds = _algo_kinds(col.events)
    assert kinds == ["algo_start", "candidate", "candidate", "candidate", "iteration", "algo_end"]
    algo = _algo_events(col.events)
    candidates = [e for e in algo if e.kind == "candidate"]
    assert all(c.payload["score"] is None for c in candidates)
    iteration = [e for e in algo if e.kind == "iteration"][0]
    assert iteration.payload["phase"] == "truncate"
    assert iteration.payload["top_indices"] == [0, 1]
    assert algo[-1].payload["top_scores"] == [None, None]


async def test_run_id_shared_with_agent_events(cfg, col) -> None:
    beam = await _make_beam(cfg, n=2)
    await beam.run(A(text="go"))

    algo_ids = {e.run_id for e in col.events if isinstance(e, AlgorithmEvent)}
    leaf_ids = {e.run_id for e in col.events if isinstance(e, AgentEvent)}
    assert len(algo_ids) == 1
    assert algo_ids == leaf_ids


# ----- debate -----------------------------------------------------------


class _Proposer(Agent[DebateContext, Proposal]):
    input = DebateContext
    output = Proposal

    def __init__(self, cfg, author: str) -> None:
        super().__init__(config=cfg, input=DebateContext, output=Proposal)
        self.author = author

    async def forward(self, x: DebateContext) -> Proposal:  # type: ignore[override]
        topic = getattr(x, "topic", "")
        return Proposal(content=f"{self.author}:{topic}", author=self.author)


class _DebateCritic(Agent[DebateTurn, Critique]):
    input = DebateTurn
    output = Critique

    async def forward(self, x: DebateTurn) -> Critique:  # type: ignore[override]
        author = x.focus.author if x.focus is not None else ""
        return Critique(target_author=author, comments="ok", score=0.7)


class _Synth(Agent[DebateRecord, Answer]):
    input = DebateRecord
    output = Answer

    async def forward(self, x: DebateRecord) -> Answer:  # type: ignore[override]
        return Answer(
            reasoning=f"{len(x.proposals)} proposals",
            answer=str(len(x.proposals)),
        )


async def test_debate_emits_round_with_lists(cfg, col) -> None:
    debate = Debate(rounds=2)
    debate.proposers = [
        await _Proposer(cfg, "alice").abuild(),
        await _Proposer(cfg, "bob").abuild(),
    ]
    debate.critic = await _DebateCritic(config=cfg).abuild()
    debate.synthesizer = await _Synth(config=cfg).abuild()
    await debate.run(DebateContext(topic="q"))

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

    sweep = Sweep({"task": ["a", "bb"], "role": ["r1", "r2"]})
    sweep.seed = seed
    await sweep.run(A(text="go"))

    kinds = _algo_kinds(col.events)
    assert kinds[0] == "algo_start"
    assert kinds[-1] == "algo_end"
    cells = [e for e in _algo_events(col.events) if e.kind == "cell"]
    assert len(cells) == 4
    assert [c.payload["cell_index"] for c in cells] == [0, 1, 2, 3]
    # score is a None placeholder; SweepCell has no native score.
    assert all(c.payload["score"] is None for c in cells)


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
    loop = VerifierLoop(threshold=0.8, max_iter=5)
    loop.generator = await _Counter(cfg).abuild()
    loop.generator.calls = 0
    loop.critic = await _ThresholdCritic(cfg, threshold=20).abuild()
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
        return Reflection(score=0.1, needs_revision=True)


async def test_auto_researcher_emits_iteration_events(cfg, col) -> None:
    async def lookup(q: Query) -> list[Hit]:
        return [Hit(text="hit", score=1.0)]

    ar = AutoResearcher(n=2, max_iter=0)
    ar.planner = await _ARPlanner(cfg).abuild()
    ar.retriever = await Retriever(lookup=lookup).abuild()
    ar.reasoner = await _ARReasoner(cfg).abuild()
    ar.critic = await _ARCritic(cfg).abuild()
    ar.reflector = await _ARReflector(cfg).abuild()

    await ar.run(Task(goal="go"))

    algo = _algo_events(col.events)
    kinds = [e.kind for e in algo]
    # algo_start + 1 iteration per attempt (n=2, no inner loop) + algo_end
    assert kinds.count("algo_start") == 1
    assert kinds.count("algo_end") == 1
    iters = [e for e in algo if e.kind == "iteration"]
    assert len(iters) == 2
    assert all(i.payload["phase"] == "reason" for i in iters)


# ----- mutation_beam ----------------------------------------------------


class _MBQ(BaseModel):
    text: str = ""


class _MBR(BaseModel):
    value: float = 0.0


class _MBLeaf(Agent[_MBQ, _MBR]):
    input = _MBQ
    output = _MBR

    async def forward(self, x: _MBQ) -> _MBR:  # type: ignore[override]
        _ = x
        temp = 0.0 if self.config is None else self.config.sampling.temperature
        return _MBR.model_construct(value=float(temp))


class _MBMetric(MetricBase):
    name = "identity"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        _ = expected
        return float(getattr(predicted, "value", 0.0))


class _MBProposer(Agent[MutationProposalInput, MutationProposalBatch]):
    input = MutationProposalInput
    output = MutationProposalBatch

    async def forward(self, x: MutationProposalInput) -> MutationProposalBatch:  # type: ignore[override]
        from operad.core.agent import _TRACER

        if _TRACER.get() is not None:
            return MutationProposalBatch()
        if x.generation_index == 0:
            return MutationProposalBatch(
                proposals=[
                    MutationProposal(op="set_temperature", temperature=0.2),
                    MutationProposal(op="set_temperature", temperature=0.9),
                ]
            )
        return MutationProposalBatch(
            proposals=[
                MutationProposal(op="set_temperature", temperature=0.8),
                MutationProposal(op="set_temperature", temperature=0.3),
            ]
        )


class _MBJudge(Agent[Candidate[MutationJudgeInput, MutationJudgeCandidate], Score]):
    input = Candidate
    output = Score

    async def forward(
        self,
        x: Candidate[MutationJudgeInput, MutationJudgeCandidate],
    ) -> Score:  # type: ignore[override]
        metric_score = 0.0 if x.output is None else x.output.metric_score
        return Score(score=metric_score, rationale="")


async def test_mutation_beam_emits_generation_events(cfg, col) -> None:
    seed = _MBLeaf(config=cfg)
    seed.config = seed.config.model_copy(
        update={"sampling": seed.config.sampling.model_copy(update={"temperature": 0.1})}
    )
    await seed.abuild()

    mb = MutationBeam(
        seed,
        metric=_MBMetric(),
        dataset=[(_MBQ(text="go"), _MBR())],
        allowed_mutations=["set_temperature"],
        branches_per_parent=2,
        frontier_size=1,
        top_k=1,
        proposer=_MBProposer(config=cfg),
        judge=_MBJudge(config=cfg),
        config=cfg,
    )
    await mb.abuild()
    await mb.run(generations=2)

    mutation_events = [
        e
        for e in _algo_events(col.events)
        if e.algorithm_path == "MutationBeam"
    ]
    assert [e.kind for e in mutation_events] == [
        "algo_start",
        "generation",
        "generation",
        "algo_end",
    ]
    generations = [e for e in mutation_events if e.kind == "generation"]
    assert len(generations) == 2
    assert all(len(g.payload["selected_candidate_ids"]) == 1 for g in generations)
    assert all(g.payload["used_judge"] is True for g in generations)


# ----- error path -------------------------------------------------------


async def test_algorithm_emits_algo_error_on_exception(cfg, col) -> None:
    beam = await _make_beam(cfg, n=1)

    async def boom(x: A) -> B:
        raise RuntimeError("boom")

    beam.generator.forward = boom  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="boom"):
        await beam.run(A(text="go"))

    algo = _algo_events(col.events)
    assert algo[0].kind == "algo_start"
    assert algo[-1].kind == "algo_error"
    assert algo[-1].payload["type"] == "RuntimeError"
    assert algo[-1].payload["message"] == "boom"
