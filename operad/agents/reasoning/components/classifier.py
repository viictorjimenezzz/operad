"""Single-label classifier leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Classifier(Agent[In, Out]):
    """Assign exactly one label to the input.

    Expects ``output`` to be a Pydantic model whose label field uses a
    constrained type (``Literal[...]``, ``Enum``), so the LLM's
    structured-output mode can only return a valid label.
    """

    role = "You are a decisive classifier that assigns exactly one label."
    task = (
        "Read the input and pick the single best-matching label from "
        "the output schema."
    )
    rules = (
        "Always return exactly one label.",
        "If the input is ambiguous, pick the most likely label rather than abstaining.",
    )
