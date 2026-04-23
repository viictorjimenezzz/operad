"""Conversational leaves — single-purpose ``Agent`` building blocks.

Each leaf has a fixed ``Utterance -> X`` contract at the class level, so
instances can be constructed simply as ``Safeguard(config=cfg)``.
"""

from __future__ import annotations

from .persona import Persona
from .safeguard import Safeguard
from .turn_taker import TurnTaker

__all__ = [
    "Persona",
    "Safeguard",
    "TurnTaker",
]
