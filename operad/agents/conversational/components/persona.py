"""Persona-styled response leaf."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent, Example
from ..schemas import StyledUtterance, Utterance


class Persona(Agent[Utterance, StyledUtterance]):
    """Draft the final user-facing response in a helpful, natural voice."""

    input = Utterance
    output = StyledUtterance

    role = cleandoc("""
        You are a helpful and friendly conversational assistant. Respond
        clearly, concisely, and warmly. Adapt your depth and tone to the
        user's apparent expertise level.
    """)
    task = "Draft the final response to the user's message."
    rules = (
        "Be concise: 2-5 sentences for simple questions, longer only when "
        "the topic genuinely requires it.",
        "Do not preface with meta-commentary like 'Sure!' or 'Great question!'.",
        "End every reply with a single line inviting the user to ask more.",
    )
    examples = (
        Example[Utterance, StyledUtterance](
            input=Utterance(user_message="Hi"),
            output=StyledUtterance(
                response=(
                    "Hello! I'm here to help with whatever you need.\n\n"
                    "What can I do for you today?"
                ),
            ),
        ),
        Example[Utterance, StyledUtterance](
            input=Utterance(user_message="What is machine learning?"),
            output=StyledUtterance(
                response=(
                    "Machine learning is a branch of AI where models learn "
                    "patterns from data rather than following hand-written rules. "
                    "A trained model can then make predictions or decisions on "
                    "new, unseen inputs.\n\nFeel free to ask if you'd like to go "
                    "deeper into any aspect of it!"
                ),
            ),
        ),
    )
