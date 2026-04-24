"""Debate domain: proposer / critic / synthesizer leaves + shared schemas.

The ``Debate`` algorithm in :mod:`operad.algorithms.debate` composes
these leaves. See :class:`operad.algorithms.Debate` for the outer
loop.
"""

from __future__ import annotations

from .components import DebateCritic, Proposer, Synthesizer
from .schemas import Critique, DebateContext, DebateRecord, DebateTurn, Proposal

__all__ = [
    "Critique",
    "DebateContext",
    "DebateCritic",
    "DebateRecord",
    "DebateTurn",
    "Proposal",
    "Proposer",
    "Synthesizer",
]
