"""Conversation-to-beliefs extractor leaf."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..shapes import Belief, Beliefs, Conversation, Turn


class BeliefExtractor(Agent[Conversation, Beliefs]):
    """Read recent turns and emit typed subject-predicate-object beliefs.

    The default contract is fixed: ``Conversation -> Beliefs``. Override
    ``task`` or ``rules`` via subclass or constructor kwargs to
    specialize (e.g. domain-specific predicates, confidence calibration).
    """

    input = Conversation
    output = Beliefs

    role = (
        "You are a precise belief extractor. You read conversations and "
        "record only claims explicitly supported by the turns."
    )
    task = (
        "Extract every belief that the conversation commits the speaker "
        "to, as subject-predicate-object triples with a confidence in "
        "[0.0, 1.0] and an optional source pointer."
    )
    rules = (
        "Never invent beliefs not supported by the turns.",
        "Prefer many small, atomic beliefs over a few compound ones.",
        "Set confidence below 0.7 when the claim is implied rather than stated.",
    )
    examples = (
        Example(
            input=Conversation(
                turns=[
                    Turn(speaker="user", text="I live in Berlin and I'm a vegetarian."),
                ]
            ),
            output=Beliefs(
                items=[
                    Belief(
                        subject="user",
                        predicate="lives_in",
                        object="Berlin",
                        confidence=0.95,
                        source="turn 0",
                    ),
                    Belief(
                        subject="user",
                        predicate="diet",
                        object="vegetarian",
                        confidence=0.95,
                        source="turn 0",
                    ),
                ]
            ),
        ),
    )
