from __future__ import annotations

"""Registry for YAML-loaded uthereal leaves.

Owner: 2-1-operad-leaves.
"""

from pathlib import Path
from typing import Any

from operad import Agent

from apps_uthereal.leaves._common import load_yaml
from apps_uthereal.leaves.context_safeguard import ContextSafeguardLeaf
from apps_uthereal.leaves.conversational_talker import ConversationalTalkerLeaf
from apps_uthereal.leaves.evidence_planner import EvidencePlannerLeaf
from apps_uthereal.leaves.fact_filter import FactFilterLeaf
from apps_uthereal.leaves.rag_talker import RAGTalkerLeaf
from apps_uthereal.leaves.reasoner import ReasonerLeaf
from apps_uthereal.leaves.retrieval_orchestrator import RetrievalOrchestratorLeaf
from apps_uthereal.leaves.rule_classifier import RuleClassifierLeaf
from apps_uthereal.leaves.safeguard_talker import SafeguardTalkerLeaf


LEAF_REGISTRY: dict[str, type[Agent[Any, Any]]] = {
    "input/agents/agent_context_safeguard.yaml": ContextSafeguardLeaf,
    "input/agents/agent_safeguard_talker.yaml": SafeguardTalkerLeaf,
    "reasoner/agents/agent_reasoner.yaml": ReasonerLeaf,
    "reasoner/agents/agent_conversational_talker.yaml": ConversationalTalkerLeaf,
    "retrieval/agents/agent_rule_classifier.yaml": RuleClassifierLeaf,
    "retrieval/agents/agent_retrieval_orchestrator.yaml": RetrievalOrchestratorLeaf,
    "retrieval/agents/agent_evidence_planner.yaml": EvidencePlannerLeaf,
    "retrieval/agents/agent_fact_filter.yaml": FactFilterLeaf,
    "retrieval/agents/agent_talker.yaml": RAGTalkerLeaf,
}

LEAF_STEP_NAMES: dict[str, str] = {
    "input/agents/agent_context_safeguard.yaml": "context_safeguard",
    "input/agents/agent_safeguard_talker.yaml": "safeguard_talker",
    "reasoner/agents/agent_reasoner.yaml": "reasoner",
    "reasoner/agents/agent_conversational_talker.yaml": "conv_talker",
    "retrieval/agents/agent_rule_classifier.yaml": "rule_classifier",
    "retrieval/agents/agent_retrieval_orchestrator.yaml": "retrieval_orchestrator",
    "retrieval/agents/agent_evidence_planner.yaml": "evidence_planner",
    "retrieval/agents/agent_fact_filter.yaml": "fact_filter",
    "retrieval/agents/agent_talker.yaml": "rag_talker",
}


def load_all_leaves(
    selfserve_root: Path,
    *,
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Agent[Any, Any]]:
    """Load and build every in-scope leaf from a selfserve YAML root."""

    leaves: dict[str, Agent[Any, Any]] = {}
    for relative_path, leaf_cls in LEAF_REGISTRY.items():
        step_name = LEAF_STEP_NAMES[relative_path]
        leaf = load_yaml(
            selfserve_root / relative_path,
            leaf_cls=leaf_cls,
            config_overrides=config_overrides,
        )
        leaves[step_name] = leaf.build()
    return leaves
