"""Typed edges for the safeguard domain."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SafeguardCategory = Literal[
    "in_scope",
    "exit",
    "separate_domain",
    "mixed_scope",
    "dangerous_or_illegal",
    "sexual_disallowed",
    "distress_self_harm",
]


class ContextInput(BaseModel):
    """Inputs for the conversation-scope safeguard classifier."""

    context: str = Field(
        default="",
        description="Agent's domain, role, purpose, and topics — the master identity profile.",
        json_schema_extra={"operad": {"system": True}},
    )
    exit_strategy: str = Field(
        default="",
        description="Conditions under which the conversation should terminate.",
        json_schema_extra={"operad": {"system": True}},
    )
    recent_chat_history: str = Field(
        default="",
        description="Recent user/agent turns, rendered as a flat string.",
    )
    message: str = Field(
        default="",
        description="The latest user message to classify.",
    )


class ContextOutput(BaseModel):
    """Decision and semantic category for a user message."""

    reason: str = Field(
        default="",
        description="Concise explanation for the decision.",
    )
    continue_field: Literal["yes", "no", "exit"] = Field(
        default="yes",
        description="'yes' accepts the message; 'no' blocks it; 'exit' ends the conversation.",
    )
    category: SafeguardCategory = Field(
        default="in_scope",
        description=(
            "Semantic class of the decision: 'in_scope', 'exit', 'separate_domain', "
            "'mixed_scope', 'dangerous_or_illegal', 'sexual_disallowed', "
            "or 'distress_self_harm'."
        ),
    )


class TalkerInput(BaseModel):
    """Inputs for generating a user-facing response to a blocked message."""

    context: str = Field(
        default="",
        description="Assistant identity, expertise, purpose, and behavioral constraints.",
        json_schema_extra={"operad": {"system": True}},
    )
    workspace_guide: str = Field(
        default="",
        description="High-level overview of the workspace's knowledge-base themes.",
        json_schema_extra={"operad": {"system": True}},
    )
    interaction_context: str = Field(
        default="",
        description="Schema descriptions for InteractionContext fields.",
        json_schema_extra={"operad": {"system": True}},
    )
    exit_strategy: str = Field(
        default="",
        description="Conditions under which the conversation terminates.",
        json_schema_extra={"operad": {"system": True}},
    )
    target_language: str = Field(
        default="",
        description="Optional language code (e.g. 'en', 'de', 'fr') for the reply.",
    )
    recent_chat_history: str = Field(
        default="",
        description="Recent conversation turns for context.",
    )
    safeguard_reason: str = Field(
        default="",
        description="Why the safeguard flagged the message, plus the rejection category.",
    )
    message: str = Field(
        default="",
        description="The user's decontextualized message.",
    )


class TextResponse(BaseModel):
    """A plain-text response produced by a talker-style agent."""

    text: str = Field(default="", description="The response body as raw text.")


__all__ = [
    "ContextInput",
    "ContextOutput",
    "SafeguardCategory",
    "TalkerInput",
    "TextResponse",
]
