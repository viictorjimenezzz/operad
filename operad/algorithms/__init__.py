"""Algorithms: outer loops that orchestrate Agents with metric feedback.

Unlike ``agents/``, nothing in this package inherits from ``Agent``.
Algorithms have their own API (``run(...)``) whose signature reflects
what the algorithm does — ``Evolutionary.run() -> Agent`` simply does
not fit the ``Agent[In, Out]`` mold.

Each algorithm's components are **class-level defaults**; callers
supply only the algorithm's own knobs at construction time. To swap
in different components, subclass and override the class attributes.
"""

from __future__ import annotations

from .autoresearch import AutoResearcher, ResearchContext, ResearchInput, ResearchPlan
from .beam import Beam
from .debate import Debate
from .sweep import Sweep, SweepCell, SweepReport
from .verifier_loop import VerifierLoop

__all__ = [
    "AutoResearcher",
    "Beam",
    "Debate",
    "ResearchContext",
    "ResearchInput",
    "ResearchPlan",
    "Sweep",
    "SweepCell",
    "SweepReport",
    "VerifierLoop",
]
