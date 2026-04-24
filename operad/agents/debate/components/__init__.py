"""Debate leaves — proposer, critic, synthesizer."""

from __future__ import annotations

from .debate_critic import DebateCritic
from .proposer import Proposer
from .synthesizer import Synthesizer

__all__ = ["DebateCritic", "Proposer", "Synthesizer"]
