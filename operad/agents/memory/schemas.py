"""Typed shapes for the memory domain.

Defined in a shared module so leaves and the store can import them
without circular dependencies between component files.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# --- Belief memory ----------------------------------------------------------


class BeliefItem(BaseModel):
    """A single atomic claim the assistant has shared with the user."""

    topic_key: str = Field(
        default="",
        description="Lowercase snake_case slug (max 80 chars) identifying the topic.",
    )
    claim_text: str = Field(
        default="",
        description="Self-contained, claim-oriented statement in one sentence.",
    )
    salience_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Priority in [0, 1]: 1.0 = direct answer; 0.1 = minor caveat.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="1-3 short topic tags for retrieval grouping.",
    )


BeliefOp = Literal["add", "update", "retract", "noop"]


class BeliefOperation(BaseModel):
    """One operation to apply to the belief state."""

    op: BeliefOp = Field(
        default="noop",
        description="'add' a new belief; 'update' an existing one; 'retract' a "
        "contradicted one; 'noop' when nothing is extractable.",
    )
    target_belief_id: str | None = Field(
        default=None,
        description="Existing belief_id for 'update' and 'retract'.",
    )
    item: BeliefItem | None = Field(
        default=None,
        description="Payload for 'add' and 'update'. Omit for 'retract' and 'noop'.",
    )
    reason: str = Field(
        default="",
        description="Short justification for the operation.",
    )


class BeliefsInput(BaseModel):
    """Inputs for the belief-state manager."""

    current_beliefs_json: str = Field(
        default="",
        description="JSON array of active belief items (belief_id, topic_key, claim_text, tags, salience_score).",
    )
    current_beliefs_summary: str = Field(
        default="",
        description="Text summary of beliefs previously shared with the user.",
    )
    turn_id: int = Field(
        default=0,
        description="The current turn identifier.",
    )
    utterance: str = Field(
        default="",
        description="The assistant's latest response that was sent to the user.",
    )


class BeliefsOutput(BaseModel):
    """Result of one round of belief-state evolution."""

    operations: list[BeliefOperation] = Field(
        default_factory=list,
        description="Operations to apply to the belief state.",
    )
    updated_summary: str = Field(
        default="",
        description="Compressed summary of all beliefs after operations, in 2-4 sentences.",
    )


# --- Session memory ---------------------------------------------------------


SessionNamespace = Literal[
    "user_background",
    "communication_preferences",
    "goals_and_intents",
    "task_context",
    "constraints",
    "interaction_state",
    "session_preferences",
]


SessionStatus = Literal["active", "tentative"]


SessionOp = Literal["add", "confirm", "revise", "supersede", "delete", "resolve", "noop"]


class SessionTarget(BaseModel):
    """Pointer to an existing or newly-proposed session-memory slot."""

    namespace: str = Field(
        default="",
        description="Session-memory namespace (e.g. 'user_background').",
    )
    slot: str = Field(
        default="",
        description="Slot name within the namespace (e.g. 'occupation').",
    )
    item_id: str | None = Field(
        default=None,
        description="Existing item_id when the operation modifies an active item.",
    )


class SessionItem(BaseModel):
    """A session-memory record proposed by an add/revise/supersede operation."""

    namespace: str = Field(
        default="",
        description="Session-memory namespace (e.g. 'user_background').",
    )
    slot: str = Field(
        default="",
        description="Slot name within the namespace.",
    )
    value: str = Field(
        default="",
        description="Raw user-provided value for the slot.",
    )
    normalized_value: str = Field(
        default="",
        description="Canonicalized form of the value.",
    )
    status: SessionStatus = Field(
        default="active",
        description="'active' when clearly stated; 'tentative' when weakly implied.",
    )


class SessionOperation(BaseModel):
    """One operation to apply to session memory."""

    op: SessionOp = Field(
        default="noop",
        description="'add', 'confirm', 'revise', 'supersede', 'delete', 'resolve', or 'noop'.",
    )
    target: SessionTarget = Field(
        default_factory=SessionTarget,
        description="The slot the operation targets.",
    )
    item: SessionItem | None = Field(
        default=None,
        description="Payload for add/revise/supersede; omit (None) for delete/resolve/noop.",
    )
    reason: str = Field(
        default="",
        description="Short justification for the operation.",
    )


class UserInput(BaseModel):
    """Inputs for the session-memory updater."""

    current_session_memory: str = Field(
        default="",
        description="Canonical session-memory state (active items, archived items, derived summary).",
    )
    recent_chat_history: str = Field(
        default="",
        description="Recent assistant-user exchanges for local disambiguation only.",
    )
    turn_id: int = Field(
        default=0,
        description="The current user turn identifier.",
    )
    user_message: str = Field(
        default="",
        description="The latest user message.",
    )


class UserOutput(BaseModel):
    """Result of one round of session-memory evolution."""

    operations: list[SessionOperation] = Field(
        default_factory=list,
        description="Operations to apply to session memory.",
    )


__all__ = [
    "BeliefItem",
    "BeliefOp",
    "BeliefOperation",
    "BeliefsInput",
    "BeliefsOutput",
    "SessionItem",
    "SessionNamespace",
    "SessionOp",
    "SessionOperation",
    "SessionStatus",
    "SessionTarget",
    "UserInput",
    "UserOutput",
]
