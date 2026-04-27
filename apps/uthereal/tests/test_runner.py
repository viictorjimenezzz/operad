from __future__ import annotations

"""End-to-end tests for ArtemisRunner.

Owner: 3-1-runner.
"""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from operad import Agent
from operad.optim.backprop import tape
from operad.runtime.observers.base import registry
from pydantic import BaseModel

from apps_uthereal.leaves.registry import LEAF_STEP_NAMES
from apps_uthereal.schemas.evidence import (
    EvidencePlannerOutput,
    FactFilterOutput,
)
from apps_uthereal.schemas.reasoner import ReasonerOutput
from apps_uthereal.schemas.retrieval import (
    ClaimItem,
    RetrievalResult,
    RetrievalSpecification,
)
from apps_uthereal.schemas.rules import (
    RetrievalOrchestratorOutput,
    RuleClassifierOutput,
)
from apps_uthereal.schemas.safeguard import ContextSafeguardResponse
from apps_uthereal.schemas.talker import (
    ConversationalTalkerOutput,
    RAGTalkerOutput,
    SafeguardTalkerOutput,
)
from apps_uthereal.schemas.workflow import (
    ArtemisInput,
    DatasetEntry,
    WorkspaceMetadata,
)
from apps_uthereal.workflow.render import (
    render_context_safeguard_input,
    render_conversational_talker_input,
    render_evidence_planner_input,
    render_fact_filter_input,
    render_rag_talker_input,
    render_reasoner_input,
    render_retrieval_orchestrator_input,
    render_rule_classifier_input,
    render_safeguard_talker_input,
)
from apps_uthereal.workflow.runner import ArtemisRunner
from apps_uthereal.workflow.state import ArtemisRunState


FIXTURES = Path(__file__).parent / "fixtures"
YAML_FIXTURES = FIXTURES / "yamls"
RUNNER_FIXTURES = FIXTURES / "runner"
BUILD_OVERRIDES = {"backend": "openai", "model": "gpt-4o-mini"}
RAG_PLAN = """reasoning: split by source
```json
[
  {
    "spec_id": "spec_b",
    "query": "beta implant protocol",
    "filter": {"labels": "beta"},
    "satisfaction_criteria": ["Find beta guidance."]
  },
  {
    "spec_id": "spec_a",
    "query": "alpha implant protocol",
    "filter": {"labels": "alpha"},
    "satisfaction_criteria": ["Find alpha guidance."]
  }
]
```"""


class ScriptedLeaf(Agent[Any, Any]):
    """Offline leaf that records inputs and returns typed scripted outputs."""

    def __init__(
        self,
        *,
        input: type[BaseModel],
        output: type[BaseModel],
        response: BaseModel,
        task: str,
    ) -> None:
        super().__init__(config=None, input=input, output=output, task=task)
        self.response = response
        self.calls: list[BaseModel] = []

    async def forward(self, x: Any) -> Any:
        self.calls.append(x)
        return self.response


class RecordingRetrieval:
    """Retrieval client that records calls and returns canned results."""

    def __init__(self) -> None:
        self.calls: list[tuple[RetrievalSpecification, str]] = []

    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        workspace_id: str,
    ) -> RetrievalResult:
        self.calls.append((spec, workspace_id))
        return RetrievalResult(
            spec_id=spec.spec_id,
            intent=spec.intent,
            satisfaction_criteria=spec.satisfaction_criteria,
            filter=spec.metadata_filter,
            text_rag_results={
                f"datasource-{spec.spec_id}": [
                    {"text": f"Retrieved fact for {spec.intent}."}
                ]
            },
            image_rag_results={},
        )

    async def get_workspace_metadata(self, workspace_id: str) -> WorkspaceMetadata:
        return WorkspaceMetadata(workspace_id=workspace_id)


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    registry.clear()
    yield
    registry.clear()


@pytest.fixture
def selfserve_root(tmp_path: Path) -> Path:
    for relative_path, step_name in LEAF_STEP_NAMES.items():
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(YAML_FIXTURES / f"{step_name}.yaml", destination)
    return tmp_path


@pytest.mark.asyncio
async def test_runner_builds(selfserve_root: Path) -> None:
    runner, _retrieval, _leaves = await _built_runner(selfserve_root)

    assert runner._built is True
    assert {node.path.split(".", 1)[-1] for node in runner._graph.nodes} >= set(
        LEAF_STEP_NAMES.values()
    )


@pytest.mark.asyncio
async def test_direct_answer_path(selfserve_root: Path) -> None:
    runner, retrieval, leaves = await _built_runner(selfserve_root)

    answer, trace = await runner.run_with_trace(_input_from_fixture("direct_answer"))

    assert answer.intent_decision == "DIRECT_ANSWER"
    assert answer.final_step == "conv_talker"
    assert answer.references is None
    assert answer.utterance == "Hello from the direct talker."
    assert retrieval.calls == []
    assert [frame.step_name for frame in trace.frames] == [
        "context_safeguard",
        "reasoner",
        "conv_talker",
    ]
    assert len(leaves["rule_classifier"].calls) == 0


@pytest.mark.asyncio
async def test_rag_path(selfserve_root: Path) -> None:
    runner, retrieval, _leaves = await _built_runner(selfserve_root, route="RAG_NEEDED")

    answer, trace = await runner.run_with_trace(_input_from_fixture("rag_needed"))

    assert answer.intent_decision == "RAG_NEEDED"
    assert answer.final_step == "rag_talker"
    assert answer.references == {"c-0": ["f-0"]}
    assert answer.utterance == "RAG answer with citations."
    assert [spec.spec_id for spec, _workspace in retrieval.calls] == [
        "spec_b",
        "spec_a",
    ]
    assert {workspace for _spec, workspace in retrieval.calls} == {"workspace-1"}
    assert [frame.step_name for frame in trace.frames] == [
        "context_safeguard",
        "reasoner",
        "rule_classifier",
        "retrieval_orchestrator",
        "evidence_planner",
        "fact_filter",
        "rag_talker",
    ]


@pytest.mark.asyncio
async def test_safeguard_rejected_path(selfserve_root: Path) -> None:
    runner, retrieval, leaves = await _built_runner(
        selfserve_root,
        safeguard_decision="no",
    )

    answer, trace = await runner.run_with_trace(
        _input_from_fixture("safeguard_rejected")
    )

    assert answer.intent_decision == "SAFEGUARD_REJECTED"
    assert answer.final_step == "safeguard_talker"
    assert answer.safeguard_category == "separate_domain"
    assert answer.utterance == "That is outside this workspace."
    assert retrieval.calls == []
    assert [frame.step_name for frame in trace.frames] == [
        "context_safeguard",
        "safeguard_talker",
    ]
    assert len(leaves["reasoner"].calls) == 0


@pytest.mark.asyncio
async def test_safeguard_exit_path(selfserve_root: Path) -> None:
    runner, retrieval, leaves = await _built_runner(
        selfserve_root,
        safeguard_decision="exit",
    )

    answer, trace = await runner.run_with_trace(_input("Please stop."))

    assert answer.intent_decision == "SAFEGUARD_REJECTED"
    assert answer.final_step == "safeguard_talker"
    assert answer.safeguard_category == "exit"
    assert retrieval.calls == []
    assert [frame.step_name for frame in trace.frames] == [
        "context_safeguard",
        "safeguard_talker",
    ]
    assert len(leaves["reasoner"].calls) == 0


@pytest.mark.asyncio
async def test_char_limit_rejected_path(selfserve_root: Path) -> None:
    runner, retrieval, leaves = await _built_runner(selfserve_root)

    answer, trace = await runner.run_with_trace(
        _input_from_fixture("char_limit_rejected")
    )

    assert answer.intent_decision == "CHAR_LIMIT_REJECTED"
    assert answer.final_step == "char_limit"
    assert answer.references is None
    assert answer.utterance == (
        "Your message is too long (12/5 characters). "
        "Please shorten it to 5 characters or fewer and try again."
    )
    assert retrieval.calls == []
    assert trace.frames == []
    assert all(not leaf.calls for leaf in leaves.values())


@pytest.mark.asyncio
async def test_replay_byte_stable(selfserve_root: Path) -> None:
    runner, _retrieval, _leaves = await _built_runner(selfserve_root)
    x = _input_from_fixture("direct_answer")

    first_answer, first_trace = await runner.run_with_trace(x)
    second_answer, second_trace = await runner.run_with_trace(x)

    assert first_trace.trace_id == second_trace.trace_id
    assert first_answer.utterance == second_answer.utterance


@pytest.mark.asyncio
async def test_trace_step_names_match_registry(selfserve_root: Path) -> None:
    runner, _retrieval, _leaves = await _built_runner(selfserve_root, route="RAG_NEEDED")

    _answer, trace = await runner.run_with_trace(_input_from_fixture("rag_needed"))

    assert {frame.step_name for frame in trace.frames} <= set(LEAF_STEP_NAMES.values())


@pytest.mark.asyncio
async def test_runner_under_tape_records_entries(selfserve_root: Path) -> None:
    runner, _retrieval, _leaves = await _built_runner(selfserve_root, route="RAG_NEEDED")

    async with tape() as t:
        _answer, trace = await runner.run_with_trace(_input_from_fixture("rag_needed"))

    assert len(t.entries) == len(trace.frames)
    assert all(entry.is_leaf for entry in t.entries)


def test_render_each_leaf_input_is_pure_function() -> None:
    state = ArtemisRunState(
        input_message="What is the protocol?",
        context="You answer from protocols.",
        workspace_guide="Guide",
        exit_strategy="Stop on request.",
        target_language="en",
        chat_history="User: hi",
        session_memory_context="user likes short answers",
        prior_beliefs_context="[]",
        rewritten_message="What is the implant protocol?",
        downstream_message="implant protocol",
        matched_rules=[{"id": "rule-1"}],
        rag_results=[
            RetrievalResult(
                spec_id="spec_0",
                intent="implant protocol",
                text_rag_results={"datasource": [{"text": "Use protocol A."}]},
            )
        ],
        collected_claims={"claims": [{"claim_id": "c-0", "claim": "Use protocol A."}]},
    )
    renderers = [
        lambda: render_context_safeguard_input(state),
        lambda: render_safeguard_talker_input(state),
        lambda: render_reasoner_input(state),
        lambda: render_conversational_talker_input(state),
        lambda: render_rule_classifier_input(state, rules=[{"id": "rule-1"}]),
        lambda: render_retrieval_orchestrator_input(
            state,
            tags=["alpha"],
            rules=[{"id": "rule-1"}],
        ),
        lambda: render_evidence_planner_input(state),
        lambda: render_fact_filter_input(state),
        lambda: render_rag_talker_input(state),
    ]

    for render in renderers:
        assert render() == render()


async def _built_runner(
    selfserve_root: Path,
    *,
    route: str = "DIRECT_ANSWER",
    safeguard_decision: str = "yes",
) -> tuple[ArtemisRunner, RecordingRetrieval, dict[str, ScriptedLeaf]]:
    retrieval = RecordingRetrieval()
    runner = ArtemisRunner(
        selfserve_root=selfserve_root,
        retrieval=retrieval,
        config_overrides=BUILD_OVERRIDES,
    )
    leaves = _scripted_leaves(
        route=route,
        safeguard_decision=safeguard_decision,
    )
    for step_name, leaf in leaves.items():
        setattr(runner, step_name, leaf)
    await runner.abuild()
    for leaf in leaves.values():
        leaf.calls.clear()
    return runner, retrieval, leaves


def _scripted_leaves(
    *,
    route: str,
    safeguard_decision: str,
) -> dict[str, ScriptedLeaf]:
    category = "in_scope"
    if safeguard_decision == "no":
        category = "separate_domain"
    elif safeguard_decision == "exit":
        category = "exit"

    return {
        "context_safeguard": ScriptedLeaf(
            input=render_context_safeguard_input(ArtemisRunState()).__class__,
            output=ContextSafeguardResponse,
            response=ContextSafeguardResponse(
                continue_field=safeguard_decision,
                reason="safeguard reason",
                category=category,
            ),
            task="context safeguard",
        ),
        "safeguard_talker": ScriptedLeaf(
            input=render_safeguard_talker_input(ArtemisRunState()).__class__,
            output=SafeguardTalkerOutput,
            response=SafeguardTalkerOutput(text="That is outside this workspace."),
            task="safeguard talker",
        ),
        "reasoner": ScriptedLeaf(
            input=render_reasoner_input(ArtemisRunState()).__class__,
            output=ReasonerOutput,
            response=ReasonerOutput(
                scratchpad="route",
                rewritten_message="Rewritten question.",
                route=route,
                route_reasoning="reason",
                downstream_message="search question",
            ),
            task="reasoner",
        ),
        "conv_talker": ScriptedLeaf(
            input=render_conversational_talker_input(ArtemisRunState()).__class__,
            output=ConversationalTalkerOutput,
            response=ConversationalTalkerOutput(text="Hello from the direct talker."),
            task="conv talker",
        ),
        "rule_classifier": ScriptedLeaf(
            input=render_rule_classifier_input(ArtemisRunState()).__class__,
            output=RuleClassifierOutput,
            response=RuleClassifierOutput(reason="match", rule_ids=["rule-1"]),
            task="rule classifier",
        ),
        "retrieval_orchestrator": ScriptedLeaf(
            input=render_retrieval_orchestrator_input(ArtemisRunState()).__class__,
            output=RetrievalOrchestratorOutput,
            response=RetrievalOrchestratorOutput(text=RAG_PLAN),
            task="retrieval orchestrator",
        ),
        "evidence_planner": ScriptedLeaf(
            input=render_evidence_planner_input(ArtemisRunState()).__class__,
            output=EvidencePlannerOutput,
            response=EvidencePlannerOutput(
                claim_sequence=[
                    ClaimItem(
                        claim_id="c-0",
                        claim="Protocol A is supported.",
                        evidence=["f-0"],
                        rationale="The fact supports the claim.",
                    )
                ]
            ),
            task="evidence planner",
        ),
        "fact_filter": ScriptedLeaf(
            input=render_fact_filter_input(ArtemisRunState()).__class__,
            output=FactFilterOutput,
            response=FactFilterOutput(fact_ids=[0]),
            task="fact filter",
        ),
        "rag_talker": ScriptedLeaf(
            input=render_rag_talker_input(ArtemisRunState()).__class__,
            output=RAGTalkerOutput,
            response=RAGTalkerOutput(text="RAG answer with citations."),
            task="rag talker",
        ),
    }


def _input_from_fixture(name: str) -> ArtemisInput:
    entry = DatasetEntry.from_json(RUNNER_FIXTURES / name / "entry.json")
    return _input_from_entry(entry)


def _input(message: str) -> ArtemisInput:
    return _input_from_entry(DatasetEntry(workspace_id="workspace-1", user_message=message))


def _input_from_entry(entry: DatasetEntry) -> ArtemisInput:
    return ArtemisInput(
        entry=entry,
        workspace=WorkspaceMetadata(
            workspace_id=entry.workspace_id,
            rules=[
                {
                    "id": "rule-1",
                    "intent_description": "Implant protocol questions.",
                    "knowhow": "Retrieve implant protocol documents.",
                }
            ],
            tags=["alpha", "beta"],
        ),
    )


def test_runner_fixture_entries_are_valid() -> None:
    for path in sorted(RUNNER_FIXTURES.glob("*/entry.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert DatasetEntry.model_validate(data).entry_id
