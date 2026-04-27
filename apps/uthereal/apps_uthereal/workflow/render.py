from __future__ import annotations

"""Per-leaf input rendering for the Artemis runner.

Owner: 3-1-runner.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from apps_uthereal.schemas.evidence import EvidencePlannerInput, FactFilterInput
from apps_uthereal.schemas.reasoner import ReasonerInput
from apps_uthereal.schemas.retrieval import RetrievalResult
from apps_uthereal.schemas.rules import (
    RetrievalOrchestratorInput,
    RuleClassifierInput,
)
from apps_uthereal.schemas.safeguard import ContextSafeguardInput
from apps_uthereal.schemas.talker import (
    ConversationalTalkerInput,
    InteractionContext,
    RAGTalkerInput,
    SafeguardTalkerInput,
)
from apps_uthereal.workflow.state import ArtemisRunState


def render_context_safeguard_input(s: ArtemisRunState) -> ContextSafeguardInput:
    """Render the context-safeguard input from run state."""

    return ContextSafeguardInput(
        context=s.context,
        recent_chat_history=s.chat_history,
        exit_strategy=s.exit_strategy,
        message=s.input_message,
    )


def render_safeguard_talker_input(s: ArtemisRunState) -> SafeguardTalkerInput:
    """Render the safeguard talker input from run state."""

    return SafeguardTalkerInput(
        target_language=s.target_language,
        context=s.context,
        workspace_guide=s.workspace_guide,
        interaction_context=render_interaction_context(),
        recent_chat_history=s.chat_history,
        exit_strategy=s.exit_strategy,
        safeguard_reason=_safeguard_reason(s),
        message=s.input_message,
    )


def render_reasoner_input(s: ArtemisRunState) -> ReasonerInput:
    """Render the central reasoner input from run state."""

    return ReasonerInput(
        context=s.context,
        interaction_context=render_interaction_context(),
        session_context=render_session_context(),
        workspace_guide=s.workspace_guide,
        user_information=s.session_memory_context,
        beliefs_json=s.prior_beliefs_context,
        belief_summary=s.prior_beliefs_context,
        chat_history=s.chat_history,
        user_message=s.input_message,
    )


def render_conversational_talker_input(
    s: ArtemisRunState,
) -> ConversationalTalkerInput:
    """Render the direct-answer talker input from run state."""

    return ConversationalTalkerInput(
        target_language=s.target_language,
        workspace_guide=s.workspace_guide,
        context=s.context,
        interaction_context=render_interaction_context(),
        session_context=render_session_context(),
        user_information=s.session_memory_context,
        beliefs=s.prior_beliefs_context,
        belief_summary=s.prior_beliefs_context,
        message=_user_facing_message(s),
    )


def render_rule_classifier_input(
    s: ArtemisRunState,
    *,
    rules: Sequence[Mapping[str, Any]] = (),
) -> RuleClassifierInput:
    """Render the rule-classifier input from state and workspace rules."""

    return RuleClassifierInput(
        rules_list=render_rules(rules),
        query=_retrieval_query(s),
    )


def render_retrieval_orchestrator_input(
    s: ArtemisRunState,
    *,
    tags: Sequence[Any] = (),
    rules: Sequence[Mapping[str, Any]] = (),
) -> RetrievalOrchestratorInput:
    """Render the retrieval-orchestrator input from state and metadata."""

    return RetrievalOrchestratorInput(
        all_labels=render_labels(tags),
        query=_retrieval_query(s),
        rules=render_rules(rules),
    )


def render_evidence_planner_input(
    s: ArtemisRunState,
    *,
    fact_ids: Sequence[int] | None = None,
) -> EvidencePlannerInput:
    """Render the evidence-planner input from retrieved facts."""

    return EvidencePlannerInput(
        query=_retrieval_query(s),
        facts=render_grouped_facts(s.rag_results, fact_ids=fact_ids),
        images=[],
    )


def render_fact_filter_input(s: ArtemisRunState) -> FactFilterInput:
    """Render the fact-filter input from retrieved facts."""

    return FactFilterInput(
        facts=render_flat_facts(s.rag_results),
        query=_retrieval_query(s),
    )


def render_rag_talker_input(s: ArtemisRunState) -> RAGTalkerInput:
    """Render the final RAG talker input from run state."""

    return RAGTalkerInput(
        interaction_context=render_interaction_context(),
        session_context=render_session_context(),
        context=s.context,
        workspace_guide=s.workspace_guide,
        content_guide="",
        target_language=s.target_language,
        user_information=s.session_memory_context,
        belief_summary=s.prior_beliefs_context,
        beliefs=s.prior_beliefs_context,
        message=_user_facing_message(s),
        matched_rules=render_rules(s.matched_rules),
        claim_sequences=s.collected_claims,
        attachments=[],
        visual_context=None,
        image_inspections=[],
    )


def render_interaction_context() -> str:
    """Render the InteractionContext field descriptions."""

    return _render_model_fields(InteractionContext)


def render_session_context() -> str:
    """Render the session-context field descriptions used by talkers."""

    return "\n".join(
        [
            "user_information: Structured facts about the user from earlier turns.",
            "belief_summary: Narrative digest of claims previously shared.",
            "beliefs: Serialized active belief items from the conversation.",
        ]
    )


def render_rules(rules: Sequence[Mapping[str, Any]]) -> str:
    """Render rules deterministically for model inputs."""

    return _canonical_json([dict(rule) for rule in rules])


def render_labels(labels: Sequence[Any]) -> str:
    """Render workspace labels deterministically for model inputs."""

    rendered: list[Any] = []
    for label in labels:
        if isinstance(label, BaseModel):
            rendered.append(label.model_dump(mode="json"))
        elif isinstance(label, Mapping):
            rendered.append(dict(label))
        else:
            rendered.append(str(label))
    return _canonical_json(rendered)


def render_flat_facts(results: Sequence[RetrievalResult]) -> str:
    """Render retrieved facts with integer fact ids for FactFilter."""

    lines: list[str] = []
    for index, fact in enumerate(_iter_text_facts(results)):
        lines.extend(
            [
                f"fact_id: {index}",
                f"text: {_fact_text(fact)}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def render_grouped_facts(
    results: Sequence[RetrievalResult],
    *,
    fact_ids: Sequence[int] | None = None,
) -> str:
    """Render retrieved facts grouped by datasource for EvidencePlanner."""

    allowed = set(fact_ids) if fact_ids is not None else None
    grouped: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    for index, datasource_id, fact in _iter_indexed_text_facts(results):
        if allowed is not None and index not in allowed:
            continue
        grouped.setdefault(datasource_id, []).append((index, fact))

    sections: list[str] = []
    for datasource_id in sorted(grouped):
        lines = [
            f"datasource_id: {datasource_id}",
            "datasource_summary: ",
            "",
        ]
        for index, fact in grouped[datasource_id]:
            lines.extend(
                [
                    f"fact_id: f-{index}",
                    f"text: {_fact_text(fact)}",
                    "",
                ]
            )
        sections.append("\n".join(lines).strip())
    return "\n\n".join(sections)


def _safeguard_reason(s: ArtemisRunState) -> str:
    category = s.safeguard_category or "generic_off_topic"
    reason = s.safeguard_reason or "request is not allowed"
    return f"{reason} ({category})"


def _user_facing_message(s: ArtemisRunState) -> str:
    return s.rewritten_message or s.input_message


def _retrieval_query(s: ArtemisRunState) -> str:
    return s.downstream_message or s.rewritten_message or s.input_message


def _render_model_fields(model_cls: type[BaseModel]) -> str:
    lines: list[str] = []
    for name, field in model_cls.model_fields.items():
        description = field.description or ""
        lines.append(f"{name}: {description}")
    return "\n".join(lines)


def _iter_text_facts(
    results: Sequence[RetrievalResult],
) -> list[Mapping[str, Any]]:
    return [fact for _, _, fact in _iter_indexed_text_facts(results)]


def _iter_indexed_text_facts(
    results: Sequence[RetrievalResult],
) -> list[tuple[int, str, Mapping[str, Any]]]:
    facts: list[tuple[int, str, Mapping[str, Any]]] = []
    index = 0
    for result in sorted(results, key=lambda item: item.spec_id):
        for datasource_id in sorted(result.text_rag_results):
            for raw_fact in result.text_rag_results[datasource_id]:
                if isinstance(raw_fact, Mapping):
                    fact = raw_fact
                else:
                    fact = {"text": str(raw_fact)}
                facts.append((index, datasource_id, fact))
                index += 1
    return facts


def _fact_text(fact: Mapping[str, Any]) -> str:
    for key in ("text", "content", "body", "value"):
        value = fact.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return _canonical_json(dict(fact))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "render_context_safeguard_input",
    "render_safeguard_talker_input",
    "render_reasoner_input",
    "render_conversational_talker_input",
    "render_rule_classifier_input",
    "render_retrieval_orchestrator_input",
    "render_evidence_planner_input",
    "render_fact_filter_input",
    "render_rag_talker_input",
    "render_interaction_context",
    "render_session_context",
    "render_rules",
    "render_labels",
    "render_flat_facts",
    "render_grouped_facts",
]
