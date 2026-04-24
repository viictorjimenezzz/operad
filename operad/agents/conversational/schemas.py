"""Typed edges for the conversational domain."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TalkerInput(BaseModel):
    """Inputs for the persona-styled conversational responder."""

    target_language: str = Field(
        default="",
        description="Optional language code for the answer (e.g. 'en', 'de', 'fr').",
    )
    workspace_guide: str = Field(
        default="",
        description="High-level overview of the workspace knowledge base.",
    )
    context: str = Field(
        default="",
        description="Assistant identity, expertise, purpose, and behavioral constraints.",
    )
    interaction_context: str = Field(
        default="",
        description="Schema descriptions for InteractionContext fields.",
    )
    session_context: str = Field(
        default="",
        description="Schema descriptions for SessionContext fields.",
    )
    user_information: str = Field(
        default="",
        description="Structured context about the user extracted from earlier turns.",
    )
    beliefs: str = Field(
        default="",
        description="Serialised list of structured beliefs from the active rolling window.",
    )
    belief_summary: str = Field(
        default="",
        description="Narrative summary of claims previously shared with the user.",
    )
    message: str = Field(
        default="",
        description="The user's decontextualized message.",
    )


class ConversationTitlerInput(BaseModel):
    """Inputs for generating a conversation-level title."""

    target_language: str = Field(
        default="",
        description="Optional language code controlling the title language.",
    )
    message: str = Field(
        default="",
        description="The first user message in the conversation.",
    )


class ConversationTitlerOutput(BaseModel):
    """Short, descriptive conversation title."""

    title: str = Field(default="", description="The title of the conversation.")


class InteractionTitlerInput(BaseModel):
    """Inputs for generating a per-interaction noun-phrase title."""

    target_language: str = Field(
        default="",
        description="Optional language code controlling the title language.",
    )
    message: str = Field(
        default="",
        description="A single user message (one interaction), already decontextualized.",
    )


class InteractionTitlerOutput(BaseModel):
    """Short, noun-phrase topic label for a single interaction."""

    title: str = Field(default="", description="The title of the interaction.")


class TextResponse(BaseModel):
    """A plain-text response produced by a talker-style agent."""

    text: str = Field(default="", description="The response body as raw text.")


__all__ = [
    "ConversationTitlerInput",
    "ConversationTitlerOutput",
    "InteractionTitlerInput",
    "InteractionTitlerOutput",
    "TalkerInput",
    "TextResponse",
]
