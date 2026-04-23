"""Conversational domain: turn-level leaves + composed conversational patterns.

Leaves live under ``components/``; composed patterns sit at the domain
root, mirroring ``operad.agents.reasoning``. ``Talker`` is the canonical
end-to-end composition: a safeguarded, persona-styled response.
"""

from __future__ import annotations

from .talker import (
    RefusalLeaf,
    SafeguardVerdict,
    StyledUtterance,
    Talker,
    TurnChoice,
    Utterance,
)
from .components import Persona, Safeguard, TurnTaker

__all__ = [
    "Persona",
    "RefusalLeaf",
    "Safeguard",
    "SafeguardVerdict",
    "StyledUtterance",
    "Talker",
    "TurnChoice",
    "TurnTaker",
    "Utterance",
]
