from __future__ import annotations

"""Vendored from
uthereal_workflow.agentic_workflows.chat.selfserve.retrieval.evidence_planning.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas._common import ImageRef, operad_extra
from apps_uthereal.schemas.retrieval import ClaimItem


class EvidencePlannerInput(BaseModel):
    """Typed input envelope for `agent_evidence_planner.yaml`."""

    query: str = Field(
        default="",
        description="User question.",
        json_schema_extra=operad_extra(system=False),
    )
    facts: str = Field(
        default="",
        description="Pre-rendered facts grouped by datasource.",
        json_schema_extra=operad_extra(system=False),
    )
    images: list[ImageRef] = Field(
        default_factory=list,
        description="Optional list of images attached as separate multimodal inputs.",
        json_schema_extra=operad_extra(system=False, modality="image"),
    )

    model_config = ConfigDict(frozen=True)


class EvidencePlannerOutput(BaseModel):
    """Typed output envelope for `agent_evidence_planner.yaml`."""

    claim_sequence: list[ClaimItem] = Field(
        default_factory=list,
        description="List of claims supported by the evidence.",
    )

    model_config = ConfigDict(frozen=True)


class FactFilterInput(BaseModel):
    """Typed input envelope for `agent_fact_filter.yaml`."""

    facts: str = Field(
        default="",
        description="Plain-text block of facts, each formatted as 'fact_id: <int>' and 'text: <content>'.",
        json_schema_extra=operad_extra(system=False),
    )
    query: str = Field(
        default="",
        description="User question.",
        json_schema_extra=operad_extra(system=False),
    )

    model_config = ConfigDict(frozen=True)


class FactFilterOutput(BaseModel):
    """Typed output envelope for `agent_fact_filter.yaml`."""

    fact_ids: list[int] = Field(default_factory=list, description="List of fact_id integers to keep.")

    model_config = ConfigDict(frozen=True)
