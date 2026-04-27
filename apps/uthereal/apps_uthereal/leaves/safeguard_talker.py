from __future__ import annotations

"""Safeguard refusal talker leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.talker import (
    SafeguardTalkerInput,
    SafeguardTalkerOutput,
)


class SafeguardTalkerLeaf(Agent[SafeguardTalkerInput, SafeguardTalkerOutput]):
    """Writes the user-facing refusal or exit response."""

    input = SafeguardTalkerInput
    output = SafeguardTalkerOutput
