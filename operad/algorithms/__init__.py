"""Algorithms: outer loops that orchestrate Agents with metric feedback.

Unlike `agents/`, nothing in this package inherits from `Agent`.
Algorithms have their own API (``run(...)``) whose signature reflects
what the algorithm does. An ``Evolutionary.run(template) -> Agent``
simply doesn't fit the ``Agent[In, Out]`` mold.
"""

from __future__ import annotations

from .best_of_n import BestOfN
from .judge import Candidate, Score
from .sweep import Sweep, SweepCell, SweepReport

__all__ = ["BestOfN", "Candidate", "Score", "Sweep", "SweepCell", "SweepReport"]
