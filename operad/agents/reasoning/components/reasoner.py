"""Chain-of-thought reasoning leaf."""

from __future__ import annotations

from ....core.agent import Agent, In, Out


class Reasoner(Agent[In, Out]):
    """Produce a chain-of-thought, then a typed answer.

    Useful whenever correctness benefits from explicit deliberation.
    Subclass with concrete `input` / `output` Pydantic classes to
    specialize; the output class is expected to include both a
    ``reasoning``-like field and a final answer field so the model
    commits to its thought process before answering.
    """

    role = "You are a careful, methodical reasoner."
    task = (
        "Work through the problem step-by-step, state any assumptions "
        "explicitly, then commit to a final answer."
    )
    rules = (
        "Show your reasoning before the final answer.",
        "Prefer uncertainty ('I don't know') over a confident wrong guess.",
    )
