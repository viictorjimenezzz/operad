"""Typed edges for the debate domain.

Shared schemas for every debate leaf and the ``Debate`` algorithm.
Kept as a leaf module in the import graph — this file imports nothing
from within ``operad.agents.debate``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DebateTopic(BaseModel):
    """What to debate.

    The concrete subject of a debate. ``topic`` is required; additional
    structure lives in ``details`` for open-ended content (stance,
    constraints, background material) without forcing every caller
    through a custom schema.
    """

    topic: str = Field(description="The question or claim to debate.")
    details: str = Field(
        default="",
        description="Optional extra context: stance, constraints, material.",
    )


class Proposal(BaseModel):
    """A single proposer's suggested answer."""

    content: str = Field(
        default="",
        description="Natural-language proposal addressing the debate topic.",
    )
    author: str = Field(
        default="",
        description="Identifier of the proposer that produced this content.",
    )


class Critique(BaseModel):
    """One critic turn: an assessment of a specific proposal."""

    target_author: str = Field(
        default="",
        description="Which proposer's content this critique addresses.",
    )
    comments: str = Field(
        default="",
        description="Natural-language assessment.",
    )
    score: float = Field(
        default=0.0,
        description="Higher-is-better numeric score for the targeted proposal.",
    )


class DebateRecord(BaseModel):
    """The accumulated state of a debate: request, proposals, critiques."""

    request: DebateTopic | None = Field(
        default=None,
        description="The original context every proposer answered.",
    )
    proposals: list[Proposal] = Field(default_factory=list)
    critiques: list[Critique] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DebateTurn(BaseModel):
    """What the critic sees on each turn: full record plus the focal proposal."""

    record: DebateRecord | None = Field(default=None)
    focus: Proposal | None = Field(
        default=None,
        description="The proposal the critic should comment on this turn.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


__all__ = [
    "Critique",
    "DebateTopic",
    "DebateRecord",
    "DebateTurn",
    "Proposal",
]
