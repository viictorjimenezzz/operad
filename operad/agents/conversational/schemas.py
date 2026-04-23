"""Typed edges for the conversational domain."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Utterance(BaseModel):
    """A single user turn together with the prior conversation."""

    user_message: str = Field(
        default="", description="The latest user message, verbatim."
    )
    history: str = Field(
        default="",
        description="Prior conversation rendered as a flat string (v1; a "
        "structured transcript is Stream I's concern).",
    )


class SafeguardVerdict(BaseModel):
    """Policy outcome for a user utterance."""

    label: Literal["allow", "block"] = Field(
        default="allow",
        description="'allow' lets the conversation proceed; 'block' triggers "
        "a polite refusal with no further model calls.",
    )
    reason: str = Field(
        default="",
        description="Short justification for the label; shown to the user "
        "when the label is 'block'.",
    )


class TurnChoice(BaseModel):
    """What the assistant should do on this turn."""

    action: Literal["respond", "clarify", "defer"] = Field(
        default="respond",
        description="'respond' answers now, 'clarify' asks a question, "
        "'defer' explains that the model cannot address this yet.",
    )
    prompt: str = Field(
        default="",
        description="Clarifying question (when action='clarify') or deferral "
        "rationale (when action='defer').",
    )


class StyledUtterance(BaseModel):
    """The assistant's final, user-facing reply."""

    response: str = Field(
        default="", description="The assistant's reply, ready to show."
    )


__all__ = [
    "SafeguardVerdict",
    "StyledUtterance",
    "TurnChoice",
    "Utterance",
]
