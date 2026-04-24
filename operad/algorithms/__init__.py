"""Algorithms: outer loops that orchestrate Agents with metric feedback.

Unlike `agents/`, nothing in this package inherits from `Agent`.
Algorithms have their own API (``run(...)``) whose signature reflects
what the algorithm does. An ``Evolutionary.run() -> Agent``
simply doesn't fit the ``Agent[In, Out]`` mold.
"""

from __future__ import annotations

from .judge import Candidate, Score
from .auto_research import AutoResearcher, ResearchInput, ResearchPlan
from .best_of_n import BestOfN
from .debate import Critique, Debate, DebateRecord, DebateTurn, Proposal
from .self_refine import RefinementInput, SelfRefine
from .sweep import Sweep, SweepCell, SweepReport
from .verifier_loop import VerifierLoop

__all__ = [
    "AutoResearcher",
    "BestOfN",
    "Candidate",
    "Critique",
    "Debate",
    "DebateRecord",
    "DebateTurn",
    "Proposal",
    "RefinementInput",
    "ResearchInput",
    "ResearchPlan",
    "Score",
    "SelfRefine",
    "Sweep",
    "SweepCell",
    "SweepReport",
    "VerifierLoop",
]
