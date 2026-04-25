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
from .talker_reasoner import (
    AssistantMessage,
    NavigationDecision,
    NavigationInput,
    NavigationKind,
    ScenarioNode,
    ScenarioTree,
    TalkerInput,
    TalkerReasoner,
    Transcript,
    Turn,
)
from .verifier_loop import VerifierLoop

__all__ = [
    "AssistantMessage",
    "AutoResearcher",
    "Beam",
    "Debate",
    "NavigationDecision",
    "NavigationInput",
    "NavigationKind",
    "ResearchContext",
    "ResearchInput",
    "ResearchPlan",
    "ScenarioNode",
    "ScenarioTree",
    "Sweep",
    "SweepCell",
    "SweepReport",
    "TalkerInput",
    "TalkerReasoner",
    "Transcript",
    "Turn",
    "VerifierLoop",
]
