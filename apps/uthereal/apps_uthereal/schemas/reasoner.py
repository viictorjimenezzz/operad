from __future__ import annotations

"""Vendored from
uthereal_workflow.agentic_workflows.chat.selfserve.reasoner.agents.agent_reasoner.yaml.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas._common import operad_extra


RouteLiteral = Literal["DIRECT_ANSWER", "RAG_NEEDED"]


class ReasonerInput(BaseModel):
    """Typed input envelope for `agent_reasoner.yaml`."""

    context: str = Field(
        default="",
        description="The assistant's identity profile - persona, expertise, tone, audience, and behavioral constraints.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    interaction_context: str = Field(
        default="",
        description="Schema descriptions for InteractionContext fields (excluding message) - consult for field semantics.",
        json_schema_extra=operad_extra(system=True),
    )
    session_context: str = Field(
        default="",
        description="Schema descriptions for SessionContext fields - consult for field semantics.",
        json_schema_extra=operad_extra(system=True),
    )
    workspace_guide: str = Field(
        default="",
        description="Concise overview of the knowledge base content.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    user_information: str = Field(
        default="",
        description="Structured information about the user extracted from previous interactions.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    beliefs_json: str = Field(
        default="",
        description="JSON array of active structured beliefs.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    belief_summary: str = Field(
        default="",
        description="Narrative digest of all claims the assistant has shared with the user.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    chat_history: str = Field(
        default="",
        description="Previous user-assistant interactions as a single string.",
        json_schema_extra=operad_extra(system=False),
    )
    user_message: str = Field(
        default="",
        description="The latest message from the user.",
        json_schema_extra=operad_extra(system=False),
    )

    model_config = ConfigDict(frozen=True)


class ReasonerOutput(BaseModel):
    """Typed output envelope for `agent_reasoner.yaml`."""

    scratchpad: str = Field(
        default="",
        description="Brief chain-of-thought route planning from the reasoner.",
    )
    rewritten_message: str = Field(
        default="",
        description="Standalone, reference-resolved version of the user's message preserving full intent.",
    )
    route: RouteLiteral = Field(default="RAG_NEEDED", description="RAG_NEEDED or DIRECT_ANSWER.")
    route_reasoning: str = Field(default="", description="Brief explanation of the routing decision.")
    downstream_message: str = Field(
        default="",
        description="Operational message for the chosen path.",
    )

    model_config = ConfigDict(frozen=True)
