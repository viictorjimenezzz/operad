from __future__ import annotations

"""Conversational talker leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.talker import (
    ConversationalTalkerInput,
    ConversationalTalkerOutput,
)


class ConversationalTalkerLeaf(
    Agent[ConversationalTalkerInput, ConversationalTalkerOutput]
):
    """Writes direct-answer responses that do not need retrieval."""

    input = ConversationalTalkerInput
    output = ConversationalTalkerOutput
