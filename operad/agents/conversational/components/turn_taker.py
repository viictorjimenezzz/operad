"""Turn-gating leaf: decides whether the bot should speak next."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent, Example
from ..schemas import TurnChoice, Utterance


class TurnTaker(Agent[Utterance, TurnChoice]):
    """Decide whether this is the right moment for the bot to respond."""

    input = Utterance
    output = TurnChoice

    role = cleandoc("""
        You are a conversation flow controller. You read the user's
        message and decide whether the assistant should respond now or
        hold back. In most cases the answer is 'respond'.
    """)
    task = cleandoc("""
        Determine whether the assistant should take this turn. Output
        'respond' to generate a reply, or 'skip' if the message is
        incomplete, purely confirmatory, or clearly intended for another
        party. Optionally provide a short additional instruction in
        'prompt' to guide the persona leaf.
    """)
    rules = (
        "Default to 'respond' unless there is a clear reason to skip.",
        "Use 'skip' only for single-character inputs, filler words, or "
        "messages obviously not directed at the bot.",
        "Keep 'prompt' empty unless a specific persona adjustment is needed.",
    )
    examples = (
        Example[Utterance, TurnChoice](
            input=Utterance(user_message="Tell me about renewable energy."),
            output=TurnChoice(action="respond", prompt=""),
        ),
        Example[Utterance, TurnChoice](
            input=Utterance(user_message="ok"),
            output=TurnChoice(action="respond", prompt=""),
        ),
        Example[Utterance, TurnChoice](
            input=Utterance(user_message="..."),
            output=TurnChoice(action="skip", prompt=""),
        ),
    )
