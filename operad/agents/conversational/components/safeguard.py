"""Content safeguard classifier for the conversational pipeline."""

from __future__ import annotations

from inspect import cleandoc

from ....core.agent import Agent, Example
from ..schemas import SafeguardVerdict, Utterance


class Safeguard(Agent[Utterance, SafeguardVerdict]):
    """Classify a user message as safe-to-process or blocked."""

    input = Utterance
    output = SafeguardVerdict

    role = cleandoc("""
        You are a content safety specialist. Your sole job is to decide
        whether the user's message is appropriate for this assistant to
        process. Err on the side of allowing: block only when the message
        is clearly harmful, illegal, or sexually inappropriate.
    """)
    task = cleandoc("""
        Classify the message as 'allow' or 'block' and provide a concise
        one-sentence reason.
    """)
    rules = (
        "Emit 'allow' unless the message contains harmful, illegal, or "
        "sexually explicit content.",
        "Do not block ambiguous, rude, or off-topic messages — only "
        "genuinely dangerous or disallowed content.",
        "Keep the reason under twenty words.",
    )
    examples = (
        Example[Utterance, SafeguardVerdict](
            input=Utterance(user_message="What is the capital of France?"),
            output=SafeguardVerdict(
                label="allow",
                reason="Benign factual question with no harmful content.",
            ),
        ),
        Example[Utterance, SafeguardVerdict](
            input=Utterance(user_message="How do I make a bomb?"),
            output=SafeguardVerdict(
                label="block",
                reason="Request for instructions on creating a dangerous weapon.",
            ),
        ),
    )
