"""Session-to-summary episodic leaf."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import Conversation, Summary, Turn


class EpisodicSummarizer(Agent[Conversation, Summary]):
    """Roll a session of turns into a short title plus a narrative summary.

    The output is suitable for dropping into a ``MemoryStore[Summary]``
    as an episodic record that can be retrieved or filtered later.
    """

    input = Conversation
    output = Summary

    role = (
        "You are a concise episodic summarizer who captures the essence "
        "of a conversation without loss of the key facts."
    )
    task = (
        "Produce a short, specific title and a narrative summary of the "
        "conversation, covering what was discussed, decided, or learned."
    )
    rules = (
        "Keep the title under eight words and specific to this episode.",
        "The summary is one short paragraph; omit greetings and filler.",
        "Preserve concrete facts (names, numbers, decisions) verbatim.",
    )
    examples = (
        Example(
            input=Conversation(
                turns=[
                    Turn(speaker="user", text="Can we move the review to Thursday?"),
                    Turn(speaker="agent", text="Yes, 3pm on Thursday works."),
                ]
            ),
            output=Summary(
                title="Review rescheduled to Thursday 3pm",
                text=(
                    "The user asked to move the review; the agent confirmed "
                    "Thursday at 3pm."
                ),
            ),
        ),
    )
