from __future__ import annotations

"""Context safeguard leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.safeguard import (
    ContextSafeguardInput,
    ContextSafeguardResponse,
)


class ContextSafeguardLeaf(Agent[ContextSafeguardInput, ContextSafeguardResponse]):
    """Routes user messages as in-scope, off-topic, unsafe, or exit."""

    input = ContextSafeguardInput
    output = ContextSafeguardResponse
