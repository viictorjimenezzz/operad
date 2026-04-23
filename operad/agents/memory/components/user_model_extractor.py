"""Conversation-to-user-model extractor leaf."""

from __future__ import annotations

from ....core.agent import Agent, Example
from ..schemas import Conversation, Turn, UserModel


class UserModelExtractor(Agent[Conversation, UserModel]):
    """Maintain a flat dictionary of known user attributes from turns.

    Designed to be run turn-by-turn or session-by-session; the output is
    a full attribute map, not a diff. Callers merge or replace the prior
    map as they see fit.
    """

    input = Conversation
    output = UserModel

    role = (
        "You are a careful user-profile extractor. You record only stable "
        "attributes the user has stated about themselves."
    )
    task = (
        "Populate a flat dictionary of user attributes (name, location, "
        "preferences, goals, ...) grounded in the conversation. Omit any "
        "attribute the user has not stated."
    )
    rules = (
        "Use short, lowercase attribute keys (e.g. 'name', 'location').",
        "Values are concise free-text strings; keep them under one short phrase.",
        "Do not infer attributes the user has not expressed.",
    )
    examples = (
        Example(
            input=Conversation(
                turns=[
                    Turn(speaker="user", text="Hi, I'm Ada and I'm learning Rust."),
                ]
            ),
            output=UserModel(
                attributes={"name": "Ada", "learning": "Rust"},
            ),
        ),
    )
