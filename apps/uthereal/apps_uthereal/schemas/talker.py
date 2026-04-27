from __future__ import annotations

"""Vendored from
uthereal_workflow.agentic_workflows.chat.selfserve.context and talker YAML inputs.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

from pydantic import BaseModel, ConfigDict, Field

from apps_uthereal.schemas._common import ImageRef, JsonValue, operad_extra


class InteractionContext(BaseModel):
    """Core variables available to conversational agent invocations."""

    message: str = Field(
        default="",
        description="The user's message after chat-aware decontextualization.",
    )
    target_language: str = Field(
        default="",
        description="ISO language code for the response language.",
    )
    context: str = Field(
        default="",
        description="The assistant's master identity profile.",
    )
    exit_strategy: str = Field(
        default="",
        description="Conditions under which the conversation should be terminated.",
    )
    workspace_guide: str = Field(
        default="",
        description="A concise, general-purpose overview of the assistant's knowledge base.",
    )

    model_config = ConfigDict(frozen=True)


class SafeguardTalkerInput(BaseModel):
    """Typed input envelope for `agent_safeguard_talker.yaml`."""

    target_language: str = Field(
        default="",
        description="Optional language code for the reply.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    context: str = Field(
        default="",
        description="The assistant's identity, expertise, purpose, and behavioral constraints.",
        json_schema_extra=operad_extra(system=True),
    )
    workspace_guide: str = Field(
        default="",
        description="High-level overview of the workspace's knowledge base themes, topics, and structure.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    interaction_context: str = Field(
        default="",
        description="Schema descriptions for InteractionContext fields - consult for field semantics.",
        json_schema_extra=operad_extra(system=True),
    )
    recent_chat_history: str = Field(
        default="",
        description="Recent conversation turns for context. May be empty.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    exit_strategy: str = Field(
        default="",
        description="Conditions under which the conversation terminates.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    safeguard_reason: str = Field(
        default="",
        description="Why the safeguard flagged the message, including the rejection category.",
        json_schema_extra=operad_extra(system=False),
    )
    message: str = Field(
        default="",
        description="The user's decontextualized message.",
        json_schema_extra=operad_extra(system=False),
    )

    model_config = ConfigDict(frozen=True)


class SafeguardTalkerOutput(BaseModel):
    """Plain-text output wrapper for `agent_safeguard_talker.yaml`."""

    text: str = Field(default="", description="The response body as raw text.")

    model_config = ConfigDict(frozen=True)


class ConversationalTalkerInput(BaseModel):
    """Typed input envelope for `agent_conversational_talker.yaml`."""

    target_language: str = Field(
        default="",
        description="Optional target language code for the answer.",
        json_schema_extra=operad_extra(system=True),
    )
    workspace_guide: str = Field(
        default="",
        description="High-level overview of the workspace's knowledge base themes, topics, and structure.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    context: str = Field(
        default="",
        description="The assistant's identity, expertise, purpose, and behavioral constraints.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    interaction_context: str = Field(
        default="",
        description="Schema descriptions for InteractionContext fields - consult for field semantics.",
        json_schema_extra=operad_extra(system=True),
    )
    session_context: str = Field(
        default="",
        description="Schema descriptions for SessionContext fields - consult for field semantics.",
        json_schema_extra=operad_extra(system=True),
    )
    user_information: str = Field(
        default="",
        description="Structured context about the user extracted from earlier turns.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    beliefs: str = Field(
        default="",
        description="Serialised list of structured beliefs from the active rolling window.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    belief_summary: str = Field(
        default="",
        description="Narrative summary of claims previously shared with the user.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    message: str = Field(
        default="",
        description="The user's decontextualized message.",
        json_schema_extra=operad_extra(system=False),
    )

    model_config = ConfigDict(frozen=True)


class ConversationalTalkerOutput(BaseModel):
    """Plain-text output wrapper for `agent_conversational_talker.yaml`."""

    text: str = Field(default="", description="The response body as raw text.")

    model_config = ConfigDict(frozen=True)


class RAGTalkerInput(BaseModel):
    """Typed input envelope for `agent_talker.yaml`."""

    interaction_context: str = Field(
        default="",
        description="Schema descriptions for InteractionContext fields - consult for field semantics.",
        json_schema_extra=operad_extra(system=True),
    )
    session_context: str = Field(
        default="",
        description="Schema descriptions for SessionContext fields - consult for field semantics.",
        json_schema_extra=operad_extra(system=True),
    )
    context: str = Field(
        default="",
        description="The assistant's identity, expertise, purpose, and behavioral constraints.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    workspace_guide: str = Field(
        default="",
        description="High-level overview of the workspace's knowledge base themes, topics, and structure.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    content_guide: str = Field(
        default="",
        description="Query-specific content guide synthesized from relevant datasource summaries.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    target_language: str = Field(
        default="",
        description="Optional target language code for the answer.",
        json_schema_extra=operad_extra(system=True),
    )
    user_information: str = Field(
        default="",
        description="Structured context about the user extracted from earlier turns.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    belief_summary: str = Field(
        default="",
        description="Narrative summary of claims previously shared with the user.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    beliefs: str = Field(
        default="",
        description="Serialised list of structured beliefs from the active rolling window.",
        json_schema_extra=operad_extra(system=True, optional=True),
    )
    message: str = Field(
        default="",
        description="The user's decontextualized message.",
        json_schema_extra=operad_extra(system=False),
    )
    matched_rules: str = Field(
        default="",
        description="Business knowledge rules for using retrieved info and framing the final response.",
        json_schema_extra=operad_extra(system=False),
    )
    claim_sequences: dict[str, list[dict[str, JsonValue]]] = Field(
        default_factory=dict,
        description="Mapping of tags to claim sequences.",
        json_schema_extra=operad_extra(system=False),
    )
    attachments: list[ImageRef] = Field(
        default_factory=list,
        description="User-provided image attachments for additional visual context.",
        json_schema_extra=operad_extra(system=False, optional=True, modality="image"),
    )
    visual_context: dict[str, JsonValue] | None = Field(
        default=None,
        description="Aggregated visual inspection context from user attachments.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )
    image_inspections: list[dict[str, JsonValue]] = Field(
        default_factory=list,
        description="Detailed per-attachment inspection results.",
        json_schema_extra=operad_extra(system=False, optional=True),
    )

    model_config = ConfigDict(frozen=True)


class RAGTalkerOutput(BaseModel):
    """Plain-text output wrapper for `agent_talker.yaml`."""

    text: str = Field(default="", description="The response body as raw text.")

    model_config = ConfigDict(frozen=True)
