"""Persona leaf: generate the final styled reply."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import StyledUtterance, Utterance


class Persona(Agent[Utterance, StyledUtterance]):
    """Produce the assistant's user-facing reply.

    The default role is deliberately generic — a helpful, concise
    assistant — so users subclass (or pass ``role=``) for specific
    voices (``TeacherPersona``, ``TerseOpsPersona``, etc.).
    """

    input = Utterance
    output = StyledUtterance

    role = "You are a helpful, concise assistant."
    task = (
        "Read the user's latest message in light of the prior history and "
        "write a reply that is accurate, on-topic, and easy to act on."
    )
    rules = (
        "Address the user's actual question; do not restate it.",
        "Be concise: no filler, no meta-commentary about the reply itself.",
        "If the answer depends on assumptions, state them briefly.",
    )
    examples = (
        Example[Utterance, StyledUtterance](
            input=Utterance(
                user_message="How do I reverse a list in Python?",
                history="",
            ),
            output=StyledUtterance(
                response="Use `list(reversed(xs))` for a new list, or "
                "`xs.reverse()` to reverse in place.",
            ),
        ),
    )
