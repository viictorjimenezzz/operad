from __future__ import annotations

"""ArtemisRunner composition for the uthereal bridge.

Owner: 3-1-runner.
"""

import asyncio
import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from operad import Agent
from operad.core.agent import _TRACER
from operad.runtime.observers.base import registry

from apps_uthereal.leaves._common import load_yaml
from apps_uthereal.leaves.registry import LEAF_REGISTRY, LEAF_STEP_NAMES
from apps_uthereal.retrieval.client import RetrievalClient
from apps_uthereal.schemas.evidence import EvidencePlannerOutput, FactFilterOutput
from apps_uthereal.schemas.reasoner import ReasonerOutput
from apps_uthereal.schemas.retrieval import (
    RetrievalResult,
    RetrievalSpecification,
    SummarizationResult,
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
from apps_uthereal.schemas.workflow import ArtemisFinalAnswer, ArtemisInput
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
from apps_uthereal.workflow.state import ArtemisRunState
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace, WorkflowTraceObserver


_CHAR_LIMIT_REJECTION_TEMPLATE = (
    "Your message is too long ({current_length}/{limit} characters). "
    "Please shorten it to {limit} characters or fewer and try again."
)
_DEFAULT_RETRIEVAL_RULE = {
    "id": "default",
    "intent_description": "Retrieve relevant information and provide an accurate answer.",
    "knowhow": "Retrieve relevant information and provide an accurate answer.",
}
_JSON_BLOCK_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_TRACE_EPOCH = datetime.fromtimestamp(0, tz=UTC)


class ArtemisRunner(Agent[ArtemisInput, ArtemisFinalAnswer]):
    """Operad-native composition equivalent to a stripped ArtemisWorkflow."""

    config = None

    def __init__(
        self,
        *,
        selfserve_root: Path,
        retrieval: RetrievalClient,
        config_overrides: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            config=None,
            input=ArtemisInput,
            output=ArtemisFinalAnswer,
        )
        self.retrieval = retrieval

        leaves = _load_runner_leaves(
            selfserve_root,
            config_overrides=config_overrides,
        )
        self.context_safeguard = leaves["context_safeguard"]
        self.safeguard_talker = leaves["safeguard_talker"]
        self.reasoner = leaves["reasoner"]
        self.conv_talker = leaves["conv_talker"]
        self.rule_classifier = leaves["rule_classifier"]
        self.retrieval_orchestrator = leaves["retrieval_orchestrator"]
        self.evidence_planner = leaves["evidence_planner"]
        self.fact_filter = leaves["fact_filter"]
        self.rag_talker = leaves["rag_talker"]

    async def forward(self, x: ArtemisInput) -> ArtemisFinalAnswer:
        """Run one stripped ArtemisWorkflow path without installing a trace observer."""

        if _TRACER.get() is not None:
            return await self._trace_all_leaves()

        state = ArtemisRunState.from_input(x)
        state.id_tenant = state.id_tenant or x.workspace.id_tenant
        state.workspace_id = state.workspace_id or x.workspace.workspace_id
        state.id_assistant = state.id_assistant or x.workspace.id_assistant

        if _exceeds_character_limit(state):
            _apply_character_limit_rejection(state)
            return state.to_final_answer()

        safeguard = (
            await self.context_safeguard(render_context_safeguard_input(state))
        ).response
        _apply_context_safeguard(state, safeguard)

        if safeguard.continue_field in {"no", "exit"}:
            refusal = (
                await self.safeguard_talker(render_safeguard_talker_input(state))
            ).response
            state.utterance = _text_response(refusal)
            state.intent_decision = "SAFEGUARD_REJECTED"
            state.final_step = "safeguard_talker"
            return state.to_final_answer()

        reasoner = (await self.reasoner(render_reasoner_input(state))).response
        _apply_reasoner(state, reasoner)

        if reasoner.route == "DIRECT_ANSWER":
            direct = (
                await self.conv_talker(render_conversational_talker_input(state))
            ).response
            state.utterance = _text_response(direct)
            state.intent_decision = "DIRECT_ANSWER"
            state.final_step = "conv_talker"
            return state.to_final_answer()

        state.intent_decision = "RAG_NEEDED"
        all_rules = [dict(rule) for rule in x.workspace.rules]

        classified = (
            await self.rule_classifier(
                render_rule_classifier_input(state, rules=all_rules)
            )
        ).response
        state.matched_rules = _match_rules(all_rules, classified)

        orchestrated = (
            await self.retrieval_orchestrator(
                render_retrieval_orchestrator_input(
                    state,
                    tags=x.workspace.tags,
                    rules=state.matched_rules,
                )
            )
        ).response
        state.retrieval_specs = _parse_retrieval_specs(
            orchestrated,
            default_query=state.downstream_message or state.rewritten_message,
        )

        state.rag_results = await self._retrieve_specs(state)

        evidence = (
            await self.evidence_planner(render_evidence_planner_input(state))
        ).response
        _apply_evidence_planner(state, evidence)

        fact_filter = (
            await self.fact_filter(render_fact_filter_input(state))
        ).response
        _apply_fact_filter(state, fact_filter)

        rag_answer = (await self.rag_talker(render_rag_talker_input(state))).response
        state.utterance = _text_response(rag_answer)
        state.final_step = "rag_talker"
        if isinstance(getattr(rag_answer, "references", None), dict):
            state.references = getattr(rag_answer, "references")
        return state.to_final_answer()

    async def run_with_trace(
        self,
        x: ArtemisInput,
    ) -> tuple[ArtemisFinalAnswer, WorkflowTrace]:
        """Run the workflow with a WorkflowTraceObserver installed.

        Uses the standard ``invoke`` envelope so any tape observer
        (operad.optim.backprop.tape) sees the runner as the tape root and
        every leaf as its child. The WorkflowTraceObserver filters non-leaf
        events out, so the on-disk trace remains leaf-only.
        """

        self.validate(x)
        run_id = x.entry.compute_entry_id()
        obs = WorkflowTraceObserver(entry_id=run_id)
        registry.register(obs)
        try:
            envelope = await self.invoke(x)
            answer = envelope.response
        finally:
            registry.unregister(obs)

        trace = _seal_runner_trace(
            obs.trace,
            root_name=self.name,
            run_id=run_id,
            final_answer_text=answer.utterance,
            intent_decision=answer.intent_decision,
        )
        return answer, trace

    async def _retrieve_specs(self, state: ArtemisRunState) -> list[RetrievalResult]:
        if not state.retrieval_specs:
            return []
        results = await asyncio.gather(
            *(
                self.retrieval.retrieve(
                    spec,
                    id_tenant=state.id_tenant,
                    id_workspace=state.workspace_id,
                    id_assistant=state.id_assistant,
                )
                for spec in state.retrieval_specs
            )
        )
        return sorted(results, key=lambda result: result.spec_id)

    async def _trace_all_leaves(self) -> ArtemisFinalAnswer:
        state = ArtemisRunState()
        await self.context_safeguard(render_context_safeguard_input(state))
        await self.safeguard_talker(render_safeguard_talker_input(state))
        await self.reasoner(render_reasoner_input(state))
        await self.conv_talker(render_conversational_talker_input(state))
        await self.rule_classifier(render_rule_classifier_input(state))
        await self.retrieval_orchestrator(render_retrieval_orchestrator_input(state))
        await self.evidence_planner(render_evidence_planner_input(state))
        await self.fact_filter(render_fact_filter_input(state))
        await self.rag_talker(render_rag_talker_input(state))
        return ArtemisFinalAnswer.model_construct()


def _exceeds_character_limit(state: ArtemisRunState) -> bool:
    return (
        state.character_limit is not None
        and len(state.input_message) > state.character_limit
    )


def _load_runner_leaves(
    selfserve_root: Path,
    *,
    config_overrides: dict[str, Any] | None,
) -> dict[str, Agent[Any, Any]]:
    leaves: dict[str, Agent[Any, Any]] = {}
    for relative_path, leaf_cls in LEAF_REGISTRY.items():
        leaves[LEAF_STEP_NAMES[relative_path]] = load_yaml(
            selfserve_root / relative_path,
            leaf_cls=leaf_cls,
            config_overrides=config_overrides,
        )
    return leaves


def _apply_character_limit_rejection(state: ArtemisRunState) -> None:
    limit = state.character_limit
    current_length = len(state.input_message)
    if limit is None:
        utterance = "Your message is too long. Please shorten it and try again."
    else:
        utterance = _CHAR_LIMIT_REJECTION_TEMPLATE.format(
            current_length=current_length,
            limit=limit,
        )
    state.intent_decision = "CHAR_LIMIT_REJECTED"
    state.utterance = utterance
    state.final_step = "char_limit"


def _apply_context_safeguard(
    state: ArtemisRunState,
    output: ContextSafeguardResponse,
) -> None:
    state.safeguard_decision = output.continue_field
    state.safeguard_reason = output.reason
    state.safeguard_category = output.category


def _apply_reasoner(state: ArtemisRunState, output: ReasonerOutput) -> None:
    state.reasoner_scratchpad = output.scratchpad
    state.rewritten_message = output.rewritten_message
    state.downstream_message = output.downstream_message
    state.route = output.route
    state.route_reasoning = output.route_reasoning


def _apply_evidence_planner(
    state: ArtemisRunState,
    output: EvidencePlannerOutput,
) -> None:
    claims = [claim.model_dump(mode="json") for claim in output.claim_sequence]
    state.collected_claims = {"claims": claims}
    state.references = {
        str(claim["claim_id"]): list(claim.get("evidence", []) or [])
        for claim in claims
        if claim.get("claim_id")
    }
    state.summarization_results = [
        SummarizationResult(
            spec_id="claims",
            intent=state.downstream_message or state.rewritten_message,
            satisfaction_criteria=[],
            filter={},
            claim_sequence=claims,
        )
    ]


def _apply_fact_filter(
    state: ArtemisRunState,
    output: FactFilterOutput,
) -> None:
    allowed_fact_ids = {f"f-{fact_id}" for fact_id in output.fact_ids}
    if not allowed_fact_ids:
        return

    filtered_claims: dict[str, list[dict[str, Any]]] = {}
    for group, claims in state.collected_claims.items():
        filtered_claims[group] = []
        for claim in claims:
            updated = dict(claim)
            evidence = updated.get("evidence", [])
            if isinstance(evidence, list):
                updated["evidence"] = _filter_evidence_ids(
                    evidence,
                    allowed_fact_ids=allowed_fact_ids,
                )
            filtered_claims[group].append(updated)
    state.collected_claims = filtered_claims

    if state.references is not None:
        state.references = {
            claim_id: _filter_evidence_ids(
                evidence if isinstance(evidence, list) else [],
                allowed_fact_ids=allowed_fact_ids,
            )
            for claim_id, evidence in state.references.items()
        }


def _filter_evidence_ids(
    evidence: Sequence[Any],
    *,
    allowed_fact_ids: set[str],
) -> list[Any]:
    return [
        item
        for item in evidence
        if not str(item).startswith("f-") or str(item) in allowed_fact_ids
    ]


def _text_response(
    output: SafeguardTalkerOutput | ConversationalTalkerOutput | RAGTalkerOutput,
) -> str:
    return output.text


def _match_rules(
    rules: Sequence[Mapping[str, Any]],
    output: RuleClassifierOutput,
) -> list[dict[str, Any]]:
    if not rules:
        return [dict(_DEFAULT_RETRIEVAL_RULE)]

    selected_ids = {str(rule_id) for rule_id in output.rule_ids}
    matched: list[dict[str, Any]] = []
    for index, rule in enumerate(rules, start=1):
        rule_id = str(rule.get("id", rule.get("rule_id", "")))
        if rule_id in selected_ids or str(index) in selected_ids:
            matched.append(dict(rule))
    return matched or [dict(_DEFAULT_RETRIEVAL_RULE)]


def _parse_retrieval_specs(
    output: RetrievalOrchestratorOutput,
    *,
    default_query: str,
) -> list[RetrievalSpecification]:
    raw_plan = _parse_json_plan(output.text)
    if isinstance(raw_plan, Mapping):
        items: Sequence[Any] = [raw_plan]
    elif isinstance(raw_plan, Sequence) and not isinstance(raw_plan, (str, bytes)):
        items = raw_plan
    else:
        items = []

    specs: list[RetrievalSpecification] = []
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, Mapping):
            continue
        query = str(raw_item.get("intent") or raw_item.get("query") or default_query)
        criteria = _criteria(raw_item.get("satisfaction_criteria"))
        raw_filter = raw_item.get("metadata_filter", raw_item.get("filter", {}))
        metadata_filter = raw_filter if isinstance(raw_filter, Mapping) else {}
        specs.append(
            RetrievalSpecification(
                spec_id=str(raw_item.get("spec_id") or f"spec_{index}"),
                intent=query,
                satisfaction_criteria=criteria,
                filter=dict(metadata_filter),
            )
        )

    if specs:
        return specs
    return [
        RetrievalSpecification(
            spec_id="spec_0",
            intent=default_query,
            satisfaction_criteria=["Answer the user question accurately."],
            filter={},
        )
    ]


def _parse_json_plan(text: str) -> Any:
    stripped = text.strip()
    match = _JSON_BLOCK_RE.search(stripped)
    if match is not None:
        stripped = match.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return []


def _criteria(raw: Any) -> list[str]:
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        items = [str(item).strip() for item in raw if str(item).strip()]
        if items:
            return items
    return ["Answer the user question accurately."]


def _seal_runner_trace(
    trace: WorkflowTrace,
    *,
    root_name: str,
    run_id: str,
    final_answer_text: str,
    intent_decision: str,
) -> WorkflowTrace:
    frames = [
        _normalize_frame(frame, root_name=root_name, run_id=run_id)
        for frame in trace.frames
    ]
    return trace.model_copy(
        update={
            "frames": frames,
            "final_answer_text": final_answer_text,
            "intent_decision": intent_decision,
        }
    ).seal()


def _normalize_frame(
    frame: TraceFrame,
    *,
    root_name: str,
    run_id: str,
) -> TraceFrame:
    step_name = _strip_root(frame.step_name, root_name=root_name)
    parent_step = _normalize_parent_step(frame.parent_step, root_name=root_name)
    return frame.model_copy(
        update={
            "step_name": step_name,
            "parent_step": parent_step,
            "run_id": run_id,
            "latency_ms": 0.0,
            "started_at": _TRACE_EPOCH,
            "finished_at": _TRACE_EPOCH,
        }
    )


def _strip_root(step_name: str, *, root_name: str) -> str:
    prefix = f"{root_name}."
    if step_name.startswith(prefix):
        return step_name[len(prefix) :]
    return step_name


def _normalize_parent_step(step_name: str | None, *, root_name: str) -> str | None:
    if step_name is None or step_name == root_name:
        return None
    return _strip_root(step_name, root_name=root_name)


__all__ = ["ArtemisRunner"]
