"""Turn-taking leaf: respond, clarify, or defer."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import TurnChoice, Utterance


class TurnTaker(Agent[Utterance, TurnChoice]):
    """Pick the next conversational move for the assistant.

    Outputs a ``TurnChoice`` with one of three actions:
    ``respond`` (answer now), ``clarify`` (ask a question back), or
    ``defer`` (explain inability). A downstream ``Switch`` on ``action``
    can branch the rest of the turn; in the current ``Talker`` wiring
    it is informational.
    """

    input = Utterance
    output = TurnChoice

    role = (
        "You are a thoughtful conversational strategist. You decide how the "
        "assistant should engage with the user's next message."
    )
    task = (
        "Given the user message and prior history, choose 'respond' to "
        "answer directly, 'clarify' when a question would unblock a better "
        "answer, or 'defer' when the assistant cannot help. When choosing "
        "'clarify', provide the exact clarifying question in 'prompt'."
    )
    rules = (
        "Prefer 'respond' when the user's intent is clear and answerable.",
        "Choose 'clarify' only when a single question would materially "
        "improve the response.",
        "Keep any clarifying prompt to one short sentence.",
    )
    examples = (
        Example[Utterance, TurnChoice](
            input=Utterance(
                user_message="Can you port this script?",
                history="",
            ),
            output=TurnChoice(
                action="clarify",
                prompt="Which language do you want it ported to?",
            ),
        ),
    )
