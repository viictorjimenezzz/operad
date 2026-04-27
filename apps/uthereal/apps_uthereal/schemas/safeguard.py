from __future__ import annotations

"""Vendored from
uthereal_workflow.agentic_workflows.chat.selfserve.input.schemas.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas._common import operad_extra


SafeguardCategory = Literal[
    "in_scope",
    "exit",
    "separate_domain",
    "mixed_scope",
    "dangerous_or_illegal",
    "sexual_disallowed",
    "distress_self_harm",
]


class ContextSafeguardInput(BaseModel):
    """Typed input envelope for `agent_context_safeguard.yaml`."""

    context: str = Field(
        default="",
        description="context field",
        json_schema_extra=operad_extra(system=False),
    )
    recent_chat_history: str = Field(
        default="",
        description="recent_chat_history field",
        json_schema_extra=operad_extra(system=False),
    )
    exit_strategy: str = Field(
        default="",
        description="exit_strategy field",
        json_schema_extra=operad_extra(system=False),
    )
    message: str = Field(
        default="",
        description="message field",
        json_schema_extra=operad_extra(system=False),
    )

    model_config = ConfigDict(frozen=True)


class ContextSafeguardResponse(BaseModel):
    """Vendored from
    uthereal_workflow.agentic_workflows.chat.selfserve.input.schemas.ContextSafeguardResponse.

    Drift is monitored by `make schemas-check`.
    """

    reason: str = Field(default="", description="The reason for your decision")
    continue_field: Literal["yes", "no", "exit"] = Field(
        default="yes",
        description="Whether to continue the workflow ('yes'), refuse ('no'), or terminate ('exit').",
    )
    category: SafeguardCategory = Field(
        default="in_scope",
        description=(
            "Semantic class of the decision: 'in_scope', 'exit', 'separate_domain', "
            "'mixed_scope', 'dangerous_or_illegal', 'sexual_disallowed', "
            "or 'distress_self_harm'."
        ),
    )

    model_config = ConfigDict(frozen=True)
