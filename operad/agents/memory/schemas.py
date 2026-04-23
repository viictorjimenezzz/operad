"""Typed shapes for the memory domain.

Defined in a shared module so leaves and the store can import them
without circular dependencies between component files.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Belief(BaseModel):
    """A single subject-predicate-object belief with provenance."""

    subject: str = Field(description="Who or what the belief is about.")
    predicate: str = Field(description="The relation connecting subject and object.")
    object: str = Field(description="The thing the subject stands in relation to.")
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in [0.0, 1.0] that this belief holds.",
    )
    source: str = Field(
        default="",
        description="Optional pointer to the turn or document the belief came from.",
    )


class Beliefs(BaseModel):
    """A batch of beliefs extracted together."""

    items: list[Belief] = Field(
        default_factory=list,
        description="The extracted beliefs, in no particular order.",
    )


class Turn(BaseModel):
    """One utterance in a conversation."""

    speaker: Literal["user", "agent"] = Field(
        description="Who produced the turn."
    )
    text: str = Field(description="The utterance text.")
    timestamp: float | None = Field(
        default=None,
        description="Optional unix timestamp of when the turn occurred.",
    )


class Conversation(BaseModel):
    """An ordered sequence of turns."""

    turns: list[Turn] = Field(
        default_factory=list,
        description="Turns in chronological order.",
    )


class UserModel(BaseModel):
    """A flat dictionary of known user attributes."""

    attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Attribute name to free-text value (e.g. 'name' -> 'Ada').",
    )


class Summary(BaseModel):
    """A narrative summary of a session or span."""

    title: str = Field(description="Short title for the summarized episode.")
    text: str = Field(description="Narrative summary of what happened.")


__all__ = [
    "Belief",
    "Beliefs",
    "Conversation",
    "Summary",
    "Turn",
    "UserModel",
]
