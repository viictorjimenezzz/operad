"""Typed edges for the reasoning domain.

Shared schemas for every reasoning leaf and composition. Kept as a
leaf module in the import graph — this file imports nothing from
within ``operad.agents.reasoning``.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

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


# --- Judge edges (shared by Critic and algorithms) -------------------------


_JIn = TypeVar("_JIn", bound=BaseModel)
_JOut = TypeVar("_JOut", bound=BaseModel)


class Score(BaseModel):
    """Judge output: a real-valued score with an optional rationale."""

    score: float = Field(
        default=0.0,
        description="Higher-is-better score assigned to the candidate.",
    )
    rationale: str = Field(
        default="",
        description="Short natural-language justification for the score.",
    )


class Candidate(BaseModel, Generic[_JIn, _JOut]):
    """Typed view a judge receives: original request + candidate answer.

    The fields are typed ``Optional[...]`` so that ``model_construct()``
    (used by the symbolic tracer to mint sentinel inputs during
    ``build()``) produces a usable Candidate. At runtime, algorithms
    populate both slots before invoking a judge; consumers may rely on
    that invariant.
    """

    input: _JIn | None = Field(
        default=None,
        description="The request that produced the candidate.",
    )
    output: _JOut | None = Field(
        default=None,
        description="A candidate answer to be judged.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- Reflector edges ---------------------------------------------------------


class ReflectionInput(BaseModel):
    original_request: str = Field(description="The user's original ask.")
    candidate_answer: str = Field(description="The prior answer to review.")


class Reflection(BaseModel):
    score: float = Field(
        description="Overall quality/confidence score for the candidate answer in [0, 1].",
    )
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
    text: str = Field(default="", description="The search query.")
    top_k: int = Field(default=5, description="Maximum number of hits to return.")


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


Args = TypeVar("Args", bound=BaseModel)
Result = TypeVar("Result", bound=BaseModel)


class ToolCall(BaseModel, Generic[Args]):
    """A typed request to invoke ``tool_name`` with structured args."""

    tool_name: str = Field(default="", description="Name of the tool to invoke.")
    # `args` is optional only so `model_construct()` yields a sentinel at
    # build time. Real call sites always construct `ToolCall[Args](...)`
    # with a concrete `args` value; `ToolUser.forward` validates it.
    args: Args | None = Field(
        default=None, description="Structured arguments for the tool."
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolResult(BaseModel, Generic[Result]):
    """A typed tool return, success-biased."""

    ok: bool = Field(description="True iff the tool ran successfully.")
    result: Result | None = Field(default=None, description="Tool return value when ok.")
    error: str = Field(default="", description="Error message when not ok.")

    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- ChatReasoner edges (chat-pipeline routing / rewriting) -----------------


class ChatReasonerInput(BaseModel):
    """Inputs for the chat-pipeline Reasoner (reference resolution + routing)."""

    context: str = Field(
        default="",
        description="Assistant identity profile — persona, expertise, tone, audience.",
        json_schema_extra={"operad": {"system": True}},
    )
    interaction_context: str = Field(
        default="",
        description="Schema descriptions for InteractionContext fields.",
        json_schema_extra={"operad": {"system": True}},
    )
    session_context: str = Field(
        default="",
        description="Schema descriptions for SessionContext fields.",
        json_schema_extra={"operad": {"system": True}},
    )
    workspace_guide: str = Field(
        default="",
        description="Concise overview of the knowledge base content and themes.",
        json_schema_extra={"operad": {"system": True}},
    )
    user_information: str = Field(
        default="",
        description="Structured information about the user extracted from prior turns.",
        json_schema_extra={"operad": {"system": True}},
    )
    beliefs_json: str = Field(
        default="",
        description="JSON array of active structured beliefs.",
    )
    belief_summary: str = Field(
        default="",
        description="Narrative digest of claims previously shared with the user.",
    )
    chat_history: str = Field(
        default="",
        description="Previous user-assistant interactions as a flat string.",
    )
    user_message: str = Field(
        default="",
        description="The latest message from the user.",
    )


ChatRoute = Literal["RAG_NEEDED", "DIRECT_ANSWER"]


class ChatReasonerOutput(BaseModel):
    """Reference-resolved message, routing decision, and search-optimized query."""

    scratchpad: str = Field(
        default="",
        description="Chain-of-thought: belief overlap, pattern classification, and routing rationale.",
    )
    rewritten_message: str = Field(
        default="",
        description="Standalone, reference-resolved version of the user's message.",
    )
    route: ChatRoute = Field(
        default="RAG_NEEDED",
        description="'RAG_NEEDED' for retrieval path; 'DIRECT_ANSWER' for conversational path.",
    )
    route_reasoning: str = Field(
        default="",
        description="Brief explanation of the routing decision.",
    )
    downstream_message: str = Field(
        default="",
        description=(
            "Operational message for the chosen path: search-optimized when RAG_NEEDED, "
            "equal to rewritten_message when DIRECT_ANSWER."
        ),
    )


__all__ = [
    "Action",
    "Answer",
    "Candidate",
    "ChatReasonerInput",
    "ChatReasonerOutput",
    "ChatRoute",
    "Choice",
    "Hit",
    "Hits",
    "Observation",
    "Query",
    "Reflection",
    "ReflectionInput",
    "RouteInput",
    "Score",
    "Task",
    "Thought",
    "ToolCall",
    "ToolResult",
]
