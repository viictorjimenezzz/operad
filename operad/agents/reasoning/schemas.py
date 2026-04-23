"""Typed edges for the reasoning domain.

Shared schemas for every reasoning leaf and composition. Kept as a
leaf module in the import graph — this file imports nothing from
within ``operad.agents.reasoning``.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


# --- ReAct edges -------------------------------------------------------------


class Task(BaseModel):
    """What the ReAct agent should accomplish."""

    goal: str = Field(description="The objective to solve.")
    context: str = Field(default="", description="Optional background information.")


class Thought(BaseModel):
    """The Reasoner's deliberation about the task."""

    reasoning: str = Field(description="Step-by-step thought about the task.")
    next_action: str = Field(
        description="Short description of the concrete next action to take."
    )


class Action(BaseModel):
    """The Actor's chosen next step, ready to be executed or simulated."""

    name: str = Field(description="The action's short name (e.g. 'search', 'compute').")
    details: str = Field(description="What this action does, with arguments.")


class Observation(BaseModel):
    """The outcome of the action, synthesized into textual form."""

    result: str = Field(description="What the action produced.")
    success: bool = Field(
        default=True, description="Whether the action appears to have succeeded."
    )


class Answer(BaseModel):
    """The Evaluator's final answer to the original task."""

    reasoning: str = Field(description="How the observation leads to the answer.")
    answer: str = Field(description="Final, concise answer to the task.")


# --- Reflector edges ---------------------------------------------------------


class ReflectionInput(BaseModel):
    original_request: str = Field(description="The user's original ask.")
    candidate_answer: str = Field(description="The prior answer to review.")


class Reflection(BaseModel):
    needs_revision: bool = Field(
        description="True iff the candidate answer should be revised.",
    )
    deficiencies: list[str] = Field(
        default_factory=list,
        description="Specific, concrete flaws in the candidate answer.",
    )
    suggested_revision: str = Field(
        default="",
        description="Revised answer; empty when needs_revision is False.",
    )


# --- Retriever edges ---------------------------------------------------------


class Hit(BaseModel):
    text: str = Field(description="The retrieved content.")
    score: float = Field(description="Relevance score in [0, 1].")
    source: str = Field(default="", description="Source identifier.")


class Query(BaseModel):
    text: str = Field(description="The search query.")
    k: int = Field(default=5, description="Maximum number of hits to return.")


class Hits(BaseModel):
    items: list[Hit] = Field(
        default_factory=list,
        description="Hits ordered by descending relevance.",
    )


# --- Router edges ------------------------------------------------------------


T = TypeVar("T")


class Choice(BaseModel, Generic[T]):
    """A typed routing decision.

    ``label`` is the chosen key; subclasses should narrow it with a
    ``Literal[...]`` parameter. ``reasoning`` is a short rationale.
    """

    label: T = Field(description="The chosen label from the allowed set.")
    reasoning: str = Field(default="", description="Short rationale for the choice.")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RouteInput(BaseModel):
    query: str = Field(description="The input to route.")


# --- ToolUser edges ----------------------------------------------------------


class ToolCall(BaseModel):
    tool_name: str = Field(default="", description="Name of the tool to invoke.")
    args: dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments passed to the tool.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolResult(BaseModel):
    ok: bool = Field(description="True iff the tool ran successfully.")
    result: Any = Field(default=None, description="Tool return value when ok.")
    error: str = Field(default="", description="Error message when not ok.")

    model_config = ConfigDict(arbitrary_types_allowed=True)


__all__ = [
    "Action",
    "Answer",
    "Choice",
    "Hit",
    "Hits",
    "Observation",
    "Query",
    "Reflection",
    "ReflectionInput",
    "RouteInput",
    "Task",
    "Thought",
    "ToolCall",
    "ToolResult",
]
