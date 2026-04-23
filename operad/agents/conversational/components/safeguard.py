"""Policy-checking leaf: allow vs. block for a user utterance."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import SafeguardVerdict, Utterance


class Safeguard(Agent[Utterance, SafeguardVerdict]):
    """Classify an utterance as safe to answer (``allow``) or not (``block``).

    Designed to feed a downstream ``Switch`` on ``label``: a rejection
    short-circuits the rest of the conversation. Subclass to bring in
    domain-specific policy (medical advice, legal advice, etc.).
    """

    input = Utterance
    output = SafeguardVerdict

    role = "You are a careful policy reviewer for a conversational assistant."
    task = (
        "Decide whether the latest user message is safe for the assistant to "
        "respond to. Emit 'allow' when a normal reply is appropriate, 'block' "
        "when the request would require unsafe, unethical, or disallowed "
        "content. Always include a short reason."
    )
    rules = (
        "Judge the user message, not the history; history is context only.",
        "Default to 'allow' for ordinary questions; reserve 'block' for "
        "clearly unsafe or disallowed requests.",
        "Keep the reason under two sentences.",
    )
    examples = (
        Example[Utterance, SafeguardVerdict](
            input=Utterance(
                user_message="What's a good sourdough hydration for a beginner?",
                history="",
            ),
            output=SafeguardVerdict(
                label="allow", reason="Benign culinary question."
            ),
        ),
    )
