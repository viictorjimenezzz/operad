from __future__ import annotations

"""Vendored from
uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.agents rule YAMLs.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

from pydantic import BaseModel, ConfigDict, Field


class RuleClassifierInput(BaseModel):
    """Typed input envelope for `agent_rule_classifier.yaml`."""

    rules_list: str = Field(
        default="",
        description="A list of available rules. Each rule has an 'id', 'intent_description'.",
    )
    query: str = Field(default="", description="The actual natural language input from the user.")

    model_config = ConfigDict(frozen=True)


class RuleClassifierOutput(BaseModel):
    """Typed output envelope for `agent_rule_classifier.yaml`."""

    reason: str = Field(default="", description="reason field")
    rule_ids: list[str] = Field(default_factory=list, description="List of rule IDs that match the query.")

    model_config = ConfigDict(frozen=True)


class RetrievalOrchestratorInput(BaseModel):
    """Typed input envelope for `agent_retrieval_orchestrator.yaml`."""

    all_labels: str = Field(default="", description="Rendered labels available for metadata filtering.")
    query: str = Field(default="", description="Search-optimized user query.")
    rules: str = Field(default="", description="Rendered matched rules.")

    model_config = ConfigDict(frozen=True)


class RetrievalOrchestratorOutput(BaseModel):
    """Plain-text output wrapper for `agent_retrieval_orchestrator.yaml`."""

    text: str = Field(default="", description="Raw JSON retrieval plan text.")

    model_config = ConfigDict(frozen=True)
