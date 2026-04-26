"""Tests for `operad.algorithms.MutationBeam`."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from operad import Agent
from operad.agents.reasoning.schemas import Candidate, Score
from operad.algorithms import MutationBeam
from operad.algorithms.mutation_beam import (
    MutationJudgeCandidate,
    MutationJudgeInput,
    MutationProposal,
    MutationProposalBatch,
    MutationProposalInput,
)
from operad.metrics.base import MetricBase


pytestmark = pytest.mark.asyncio


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    value: float = 0.0


class _TempLeaf(Agent[Q, R]):
    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        _ = x
        temp = 0.0 if self.config is None else self.config.sampling.temperature
        return R.model_construct(value=float(temp))


class _IdentityMetric(MetricBase):
    name = "identity"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        _ = expected
        return float(getattr(predicted, "value", 0.0))


class _MappedProposer(Agent[MutationProposalInput, MutationProposalBatch]):
    input = MutationProposalInput
    output = MutationProposalBatch

    def __init__(self, cfg, mapping: dict[tuple[int, int], list[MutationProposal]]) -> None:
        super().__init__(
            config=cfg,
            input=MutationProposalInput,
            output=MutationProposalBatch,
        )
        self.mapping = mapping

    async def forward(self, x: MutationProposalInput) -> MutationProposalBatch:  # type: ignore[override]
        from operad.core.agent import _TRACER

        if _TRACER.get() is not None:
            return MutationProposalBatch()
        key = (x.generation_index, x.parent_index)
        return MutationProposalBatch(proposals=list(self.mapping.get(key, [])))


class _JudgeByMetric(Agent[Candidate[MutationJudgeInput, MutationJudgeCandidate], Score]):
    input = Candidate
    output = Score

    async def forward(
        self,
        x: Candidate[MutationJudgeInput, MutationJudgeCandidate],
    ) -> Score:  # type: ignore[override]
        metric_score = 0.0
        if x.output is not None:
            metric_score = float(x.output.metric_score)
        return Score(score=metric_score, rationale="")


async def test_mutation_beam_applies_typed_set_temperature(cfg) -> None:
    seed = _TempLeaf(config=cfg)
    seed.config = seed.config.model_copy(update={"sampling": seed.config.sampling.model_copy(update={"temperature": 0.0})})
    await seed.abuild()

    proposer = _MappedProposer(
        cfg,
        {
            (0, 0): [
                MutationProposal(op="set_temperature", temperature=0.8, rationale="raise"),
                MutationProposal(op="set_temperature", temperature=0.3, rationale="lower"),
            ]
        },
    )

    algo = MutationBeam(
        seed,
        metric=_IdentityMetric(),
        dataset=[(Q(text="x"), R())],
        allowed_mutations=["set_temperature"],
        branches_per_parent=2,
        frontier_size=1,
        top_k=1,
        proposer=proposer,
    )
    await algo.abuild()
    report = await algo.run(generations=1)

    assert len(report.generations) == 1
    gen0 = report.generations[0]
    assert gen0.produced == 2
    assert gen0.kept == 1
    assert gen0.candidates[0].op == "set_temperature"
    assert seed.config.sampling.temperature == pytest.approx(0.8)


async def test_mutation_beam_two_generation_frontier_growth(cfg) -> None:
    seed = _TempLeaf(config=cfg)
    seed.config = seed.config.model_copy(update={"sampling": seed.config.sampling.model_copy(update={"temperature": 0.1})})
    await seed.abuild()

    proposer = _MappedProposer(
        cfg,
        {
            (0, 0): [
                MutationProposal(op="set_temperature", temperature=0.2),
                MutationProposal(op="set_temperature", temperature=0.4),
            ],
            (1, 0): [
                MutationProposal(op="set_temperature", temperature=0.6),
                MutationProposal(op="set_temperature", temperature=0.8),
            ],
            (1, 1): [
                MutationProposal(op="set_temperature", temperature=0.7),
                MutationProposal(op="set_temperature", temperature=0.9),
            ],
        },
    )

    algo = MutationBeam(
        seed,
        metric=_IdentityMetric(),
        dataset=[(Q(text="x"), R())],
        allowed_mutations=["set_temperature"],
        branches_per_parent=2,
        frontier_size=2,
        top_k=2,
        proposer=proposer,
    )
    await algo.abuild()
    report = await algo.run(generations=2)

    assert len(report.generations) == 2
    assert report.generations[0].produced == 2
    assert report.generations[1].produced == 4
    assert report.final_frontier_size == 2


async def test_mutation_beam_judge_selection_honors_top_k(cfg) -> None:
    seed = _TempLeaf(config=cfg)
    seed.config = seed.config.model_copy(update={"sampling": seed.config.sampling.model_copy(update={"temperature": 0.1})})
    await seed.abuild()

    proposer = _MappedProposer(
        cfg,
        {
            (0, 0): [
                MutationProposal(op="set_temperature", temperature=0.2, rationale="small"),
                MutationProposal(op="set_temperature", temperature=0.9, rationale="large"),
            ]
        },
    )

    algo = MutationBeam(
        seed,
        metric=_IdentityMetric(),
        dataset=[(Q(text="x"), R())],
        allowed_mutations=["set_temperature"],
        branches_per_parent=2,
        frontier_size=1,
        top_k=1,
        proposer=proposer,
        judge=_JudgeByMetric(config=cfg),
        config=cfg,
    )
    await algo.abuild()
    report = await algo.run(generations=1)

    gen0 = report.generations[0]
    assert gen0.kept == 1
    assert len(gen0.selected_candidate_ids) == 1
    best_metric = max(c.metric_score for c in gen0.candidates)
    selected_id = gen0.selected_candidate_ids[0]
    selected = next(c for c in gen0.candidates if c.candidate_id == selected_id)
    assert selected.metric_score == pytest.approx(best_metric)
    assert seed.config.sampling.temperature == pytest.approx(0.9)
