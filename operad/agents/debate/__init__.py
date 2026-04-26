"""Debate domain: proposer / critic / synthesizer leaves + shared schemas.

The ``Debate`` algorithm in :mod:`operad.algorithms.debate` composes
these leaves. See :class:`operad.algorithms.Debate` for the outer
loop.
"""

from __future__ import annotations

from .components import DebateCritic, Proposer, Synthesizer
from .schemas import Critique, DebateRecord, DebateTopic, DebateTurn, Proposal

__all__ = [
    "Critique",
    "DebateCritic",
    "DebateRecord",
    "DebateTopic",
    "DebateTurn",
    "Proposal",
    "Proposer",
    "Synthesizer",
]
