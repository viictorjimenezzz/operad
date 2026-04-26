"""MutationBeam: evolve an agent with LLM-proposed typed mutations.

Each generation expands a frontier of parent agents. For every parent, a
parallel bank of ReAct branches proposes concrete mutation arguments; valid
mutations are applied to cloned children, then scored on a dataset metric.

Selection has two modes:
- judge mode: rank candidates through ``Beam`` (top-k by judge score)
- no-judge mode: keep proposal order (first top-k)

The best selected child is written back onto the seed root so callers can keep
using the original agent reference.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from inspect import cleandoc
from typing import Any, Literal, Sequence

from pydantic import BaseModel, Field

from ..agents.core.pipelines import Parallel, Sequential
from ..agents.reasoning.components import Reasoner
from ..agents.reasoning.react import ReAct
from ..agents.reasoning.schemas import Answer, Candidate, Score, Task
from ..benchmark.evaluate import evaluate
from ..core.agent import Agent, _TRACER
from ..metrics.base import Metric
from ..runtime.observers.base import _enter_algorithm_run, emit_algorithm_event
from ..utils.ops import AppendRule, DropRule, Op, ReplaceRule, SetTemperature
from .beam import Beam


AllowedMutation = Literal[
    "set_temperature",
    "append_rule",
    "replace_rule",
    "drop_rule",
]


class MutationProposal(BaseModel):
    op: AllowedMutation = Field(description="Mutation kind.")
    rationale: str = Field(default="", description="Why this mutation was chosen.")
    temperature: float | None = Field(
        default=None,
        description="Target temperature for set_temperature.",
    )
    rule: str = Field(default="", description="Rule text for append/replace ops.")
    index: int | None = Field(
        default=None,
        description="Rule index for replace/drop ops.",
    )


class MutationProposalInput(BaseModel):
    generation_index: int = Field(default=0)
    parent_index: int = Field(default=0)
    parent_summary: str = Field(default="")
    allowed_mutations: list[AllowedMutation] = Field(default_factory=list)


class MutationProposalBatch(BaseModel):
    proposals: list[MutationProposal] = Field(default_factory=list)


class MutationJudgeInput(BaseModel):
    objective: str = Field(default="Select the strongest mutation candidate.")
    generation_index: int = Field(default=0)


class MutationJudgeCandidate(BaseModel):
    candidate_id: int = Field(default=-1)
    summary: str = Field(default="")
    metric_score: float = Field(default=0.0)
    score: float | None = Field(
        default=None,
        description="Judge score injected by Beam when a judge is present.",
    )


class MutationCandidate(BaseModel):
    candidate_id: int = Field(default=-1)
    parent_index: int = Field(default=-1)
    op: AllowedMutation = Field(default="append_rule")
    rationale: str = Field(default="")
    metric_score: float = Field(default=0.0)
    score: float | None = Field(default=None)
    hash_content: str = Field(default="")


class MutationGeneration(BaseModel):
    generation_index: int = Field(default=0)
    produced: int = Field(default=0)
    kept: int = Field(default=0)
    used_judge: bool = Field(default=False)
    selected_candidate_ids: list[int] = Field(default_factory=list)
    candidates: list[MutationCandidate] = Field(default_factory=list)


class MutationBeamReport(BaseModel):
    generations: list[MutationGeneration] = Field(default_factory=list)
    final_hash: str = Field(default="")
    final_frontier_size: int = Field(default=0)


class _QueueCandidateGenerator(Agent[MutationJudgeInput, MutationJudgeCandidate]):
    """Deterministic generator used to rank a fixed candidate list via Beam."""

    input = MutationJudgeInput
    output = MutationJudgeCandidate

    def __init__(self, cfg: Any, queue: list[MutationJudgeCandidate]) -> None:
        super().__init__(config=cfg, input=MutationJudgeInput, output=MutationJudgeCandidate)
        self._queue = queue
        self._idx = 0

    async def forward(self, x: MutationJudgeInput) -> MutationJudgeCandidate:  # type: ignore[override]
        _ = x
        if _TRACER.get() is not None:
            return MutationJudgeCandidate()
        if not self._queue:
            return MutationJudgeCandidate()
        if self._idx >= len(self._queue):
            return self._queue[-1]
        item = self._queue[self._idx]
        self._idx += 1
        return item


@dataclass
class _CandidateState:
    agent: Agent[Any, Any]
    summary: MutationCandidate
    judge_payload: MutationJudgeCandidate


def _combine_proposals(values: dict[str, BaseModel]) -> MutationProposalBatch:
    proposals: list[MutationProposal] = []
    for key in sorted(values):
        v = values[key]
        if isinstance(v, MutationProposal):
            proposals.append(v)
    return MutationProposalBatch(proposals=proposals)


class MutationBeam:
    """Two-loop mutation search with typed proposals and optional Beam judging."""

    def __init__(
        self,
        seed: Agent[Any, Any],
        *,
        metric: Metric,
        dataset: list[tuple[Any, Any]],
        allowed_mutations: Sequence[AllowedMutation],
        branches_per_parent: int = 3,
        frontier_size: int = 2,
        top_k: int = 2,
        context: str = "",
        judge: Agent[Candidate[MutationJudgeInput, MutationJudgeCandidate], Score]
        | None = None,
        judge_context: str = "",
        config: Any | None = None,
        proposer: Agent[MutationProposalInput, MutationProposalBatch] | None = None,
    ) -> None:
        if not dataset:
            raise ValueError("dataset must not be empty")
        if branches_per_parent < 1:
            raise ValueError("branches_per_parent must be >= 1")
        if frontier_size < 1:
            raise ValueError("frontier_size must be >= 1")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if not allowed_mutations:
            raise ValueError("allowed_mutations must not be empty")

        self._root = seed
        self.metric = metric
        self.dataset = list(dataset)
        self.allowed_mutations = list(allowed_mutations)
        self.branches_per_parent = branches_per_parent
        self.frontier_size = frontier_size
        self.top_k = top_k
        self.context = context
        self._config = config or seed.config
        if self._config is None and proposer is None:
            raise ValueError(
                "MutationBeam needs either config/seed.config or a custom proposer"
            )

        self._proposer = proposer or self._build_default_proposer()
        self._judge = judge.clone(context=judge_context) if judge is not None else None
        self._frontier: list[Agent[Any, Any]] = [seed]

    def _build_default_proposer(self) -> Agent[MutationProposalInput, MutationProposalBatch]:
        children: dict[str, Agent[MutationProposalInput, MutationProposal]] = {}
        for i in range(self.branches_per_parent):
            branch_context = f"{self.context}\n\nmutation_branch={i}"
            planner = Reasoner(
                config=self._config,
                input=MutationProposalInput,
                output=Task,
                role="You plan a concrete mutation candidate.",
                task=(
                    "Read the parent summary and choose one mutation from "
                    "allowed_mutations that is likely to improve quality."
                ),
                rules=(
                    "Always name exactly one allowed mutation kind.",
                    "Prefer diversity across different branches.",
                    "Include concrete numeric/string values to execute the mutation.",
                ),
            )
            reactor = ReAct(config=self._config, context=branch_context)
            extractor = Reasoner(
                config=self._config,
                input=Answer,
                output=MutationProposal,
                role="You convert reasoning output into a typed mutation proposal.",
                task=(
                    "Return a single MutationProposal with concrete args. "
                    "Do not invent unsupported fields."
                ),
                rules=(
                    "op must be one of: set_temperature, append_rule, replace_rule, drop_rule.",
                    "For set_temperature, include temperature.",
                    "For append_rule/replace_rule, include non-empty rule.",
                    "For replace_rule/drop_rule, include index.",
                ),
            )
            children[f"branch_{i}"] = Sequential(
                planner,
                reactor,
                extractor,
                input=MutationProposalInput,
                output=MutationProposal,
                name=f"mutation_branch_{i}",
            )

        return Parallel(
            children,
            input=MutationProposalInput,
            output=MutationProposalBatch,
            combine=_combine_proposals,
            name="mutation_proposer_parallel",
        )

    async def abuild(self) -> "MutationBeam":
        await self._proposer.abuild()
        if self._judge is not None:
            await self._judge.abuild()
        return self

    async def run(self, *, generations: int) -> MutationBeamReport:
        if generations < 1:
            raise ValueError("generations must be >= 1")

        path = type(self).__name__
        started = time.time()
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "algo_start",
                algorithm_path=path,
                payload={
                    "generations": generations,
                    "branches_per_parent": self.branches_per_parent,
                    "frontier_size": self.frontier_size,
                    "top_k": self.top_k,
                    "allowed_mutations": list(self.allowed_mutations),
                    "judge_enabled": self._judge is not None,
                },
                started_at=started,
            )
            try:
                report = await self._run_impl(generations=generations)
                await emit_algorithm_event(
                    "algo_end",
                    algorithm_path=path,
                    payload={
                        "generations": len(report.generations),
                        "final_hash": report.final_hash,
                        "final_frontier_size": report.final_frontier_size,
                    },
                    started_at=started,
                    finished_at=time.time(),
                )
                return report
            except Exception as e:
                await emit_algorithm_event(
                    "algo_error",
                    algorithm_path=path,
                    payload={"type": type(e).__name__, "message": str(e)},
                    started_at=started,
                    finished_at=time.time(),
                )
                raise

    async def _run_impl(self, *, generations: int) -> MutationBeamReport:
        frontier = list(self._frontier)
        generation_reports: list[MutationGeneration] = []
        candidate_id = 0

        for gen_idx in range(generations):
            produced: list[_CandidateState] = []
            for parent_index, parent in enumerate(frontier):
                proposal_input = MutationProposalInput(
                    generation_index=gen_idx,
                    parent_index=parent_index,
                    parent_summary=self._parent_summary(parent),
                    allowed_mutations=list(self.allowed_mutations),
                )
                batch = (await self._proposer(proposal_input)).response
                for proposal in batch.proposals:
                    created = await self._spawn_candidate(
                        candidate_id=candidate_id,
                        parent_index=parent_index,
                        parent=parent,
                        proposal=proposal,
                    )
                    candidate_id += 1
                    if created is not None:
                        produced.append(created)

            selected = await self._select(produced, generation_index=gen_idx)
            if selected:
                frontier = [c.agent for c in selected[: self.frontier_size]]
                self._frontier = frontier
                await self._write_back(selected[0].agent)

            generation = MutationGeneration(
                generation_index=gen_idx,
                produced=len(produced),
                kept=len(selected),
                used_judge=self._judge is not None,
                selected_candidate_ids=[c.summary.candidate_id for c in selected],
                candidates=[c.summary for c in produced],
            )
            generation_reports.append(generation)

            await emit_algorithm_event(
                "generation",
                algorithm_path=type(self).__name__,
                payload=generation.model_dump(mode="json"),
            )

            if not produced:
                break

        return MutationBeamReport(
            generations=generation_reports,
            final_hash=self._root.hash_content,
            final_frontier_size=len(frontier),
        )

    def _parent_summary(self, agent: Agent[Any, Any]) -> str:
        cfg = agent.config
        temp = None if cfg is None else cfg.sampling.temperature
        allowed = ", ".join(self.allowed_mutations)
        return cleandoc(
            f"""
            role: {agent.role!r}
            task: {agent.task!r}
            rules: {list(agent.rules)!r}
            temperature: {temp!r}
            allowed_mutations: {allowed}
            """
        )

    async def _spawn_candidate(
        self,
        *,
        candidate_id: int,
        parent_index: int,
        parent: Agent[Any, Any],
        proposal: MutationProposal,
    ) -> _CandidateState | None:
        if proposal.op not in self.allowed_mutations:
            return None

        candidate = parent.clone()
        op = self._proposal_to_op(candidate, proposal)
        if op is None:
            return None

        try:
            op.apply(candidate)
            await candidate.abuild()
            report = await evaluate(candidate, self.dataset, [self.metric])
        except Exception:
            return None

        metric_score = float(report.summary[self.metric.name])
        summary = MutationCandidate(
            candidate_id=candidate_id,
            parent_index=parent_index,
            op=proposal.op,
            rationale=proposal.rationale,
            metric_score=metric_score,
            hash_content=candidate.hash_content,
        )
        judge_payload = MutationJudgeCandidate(
            candidate_id=candidate_id,
            metric_score=metric_score,
            summary=self._candidate_summary(summary, proposal),
        )
        return _CandidateState(
            agent=candidate,
            summary=summary,
            judge_payload=judge_payload,
        )

    @staticmethod
    def _candidate_summary(summary: MutationCandidate, proposal: MutationProposal) -> str:
        details = []
        if proposal.temperature is not None:
            details.append(f"temperature={proposal.temperature:.2f}")
        if proposal.rule:
            details.append(f"rule={proposal.rule!r}")
        if proposal.index is not None:
            details.append(f"index={proposal.index}")
        suffix = ", ".join(details)
        return (
            f"candidate_id={summary.candidate_id}; op={summary.op}; "
            f"metric_score={summary.metric_score:.4f}; {suffix}; "
            f"rationale={proposal.rationale}"
        )

    @staticmethod
    def _proposal_to_op(agent: Agent[Any, Any], proposal: MutationProposal) -> Op | None:
        if proposal.op == "set_temperature":
            if proposal.temperature is None or agent.config is None:
                return None
            temperature = max(0.0, min(float(proposal.temperature), 2.0))
            return SetTemperature(path="", temperature=temperature)

        if proposal.op == "append_rule":
            rule = proposal.rule.strip()
            if not rule:
                return None
            return AppendRule(path="", rule=rule)

        if proposal.op == "replace_rule":
            if not agent.rules:
                return None
            rule = proposal.rule.strip()
            if not rule:
                return None
            idx = int(proposal.index or 0) % len(agent.rules)
            return ReplaceRule(path="", index=idx, rule=rule)

        if proposal.op == "drop_rule":
            if not agent.rules:
                return None
            idx = int(proposal.index if proposal.index is not None else len(agent.rules) - 1)
            idx %= len(agent.rules)
            return DropRule(path="", index=idx)

        return None

    async def _select(
        self,
        candidates: list[_CandidateState],
        *,
        generation_index: int,
    ) -> list[_CandidateState]:
        if not candidates:
            return []

        limit = min(self.top_k, len(candidates))
        if self._judge is None:
            return candidates[:limit]

        judge_inputs = [c.judge_payload for c in candidates]
        generator = await _QueueCandidateGenerator(self._config, judge_inputs).abuild()

        beam = Beam[MutationJudgeInput, MutationJudgeCandidate](
            n=len(judge_inputs),
            top_k=limit,
            criteria=(
                "Prefer candidates that improve quality while remaining concise; "
                "higher metric_score is usually better."
            ),
        )
        beam.generator = generator
        beam.judge = self._judge
        ranked = await beam.run(
            MutationJudgeInput(
                generation_index=generation_index,
                objective="Select the strongest mutation candidates.",
            )
        )

        by_id = {c.summary.candidate_id: c for c in candidates}
        selected: list[_CandidateState] = []
        for item in ranked:
            chosen = by_id.get(item.candidate_id)
            if chosen is None:
                continue
            chosen.summary.score = item.score
            selected.append(chosen)
        return selected[:limit]

    async def _write_back(self, best: Agent[Any, Any]) -> None:
        self._root.load_state(best.state())
        await self._root.abuild()


__all__ = [
    "AllowedMutation",
    "MutationBeam",
    "MutationBeamReport",
    "MutationCandidate",
    "MutationGeneration",
    "MutationProposal",
]
