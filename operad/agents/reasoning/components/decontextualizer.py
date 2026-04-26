"""Conversation decontextualization leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Decontextualizer(Agent[In, Out]):
    """Rewrite an input into a stand-alone, context-complete form."""

    role = "You are an expert at decontextualizing text."
    task = (
        "Rewrite the input into a stand-alone version that preserves intent, "
        "fills in missing referents, and removes dependence on prior turns."
    )
    rules = (
        "Keep meaning and constraints unchanged.",
        "Resolve pronouns and references when possible.",
        "Do not add facts that are not implied by the input.",
    )
    default_sampling = {"temperature": 0.2}
