"""Concise summarization leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Summarizer(Agent[In, Out]):
    """Summarize input content into a compact, high-signal output."""

    role = "You are a careful summarizer."
    task = (
        "Summarize the input into the target output schema, keeping only the "
        "most important information."
    )
    rules = (
        "Prioritize concrete facts over stylistic flourishes.",
        "Keep the summary concise and readable.",
        "Avoid dropping critical constraints or decisions.",
    )
    default_sampling = {"temperature": 0.2}
