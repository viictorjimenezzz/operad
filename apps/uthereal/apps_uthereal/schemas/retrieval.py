from __future__ import annotations

"""Vendored from
uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.schemas.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas._common import JsonValue


class RetrievalSpecification(BaseModel):
    """Vendored retrieval branch specification."""

    spec_id: str = Field(default="", description="Unique identifier for this retrieval specification/branch.")
    intent: str = Field(default="", description="The intent to retrieve.")
    satisfaction_criteria: list[str] = Field(
        default_factory=list,
        description="Criteria used to evaluate completeness and correctness of retrieved information.",
    )
    metadata_filter: dict[str, JsonValue] = Field(
        default_factory=dict,
        alias="filter",
        description="Mongo-like metadata filter to apply during retrieval.",
    )

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class RetrievalResult(RetrievalSpecification):
    """Vendored retrieval branch after RAG has executed."""

    text_rag_results: dict[str, list[dict[str, JsonValue]]] = Field(
        default_factory=dict,
        description="Retrieved text information keyed by datasource id.",
    )
    image_rag_results: dict[str, list[dict[str, JsonValue]]] = Field(
        default_factory=dict,
        description="Retrieved image information keyed by datasource id.",
    )

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class SummarizationResult(RetrievalResult):
    """Vendored retrieval branch after evidence planning."""

    claim_sequence: list[dict[str, JsonValue]] = Field(
        default_factory=list,
        description="Sequence of claims with evidence IDs for this branch.",
    )

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class ClaimItem(BaseModel):
    """Vendored from
    uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.evidence_planning.ClaimItem.

    Drift is monitored by `make schemas-check`.
    """

    claim_id: str = Field(default="", description="Unique identifier for the claim (e.g., c-0).")
    scratchpad: str = Field(
        default="",
        description="Brief working notes discussing how this claim was constructed.",
    )
    claim: str = Field(default="", description="The claim being made.")
    evidence: list[str] = Field(
        default_factory=list,
        description="List of fact/image IDs that support this claim or were used to derive it.",
    )
    rationale: str = Field(default="", description="Brief explanation of why the cited evidence supports this claim.")

    model_config = ConfigDict(frozen=True)
