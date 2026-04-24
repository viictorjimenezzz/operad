"""Debate critic leaf: scores one focal proposal against the full record."""

from __future__ import annotations

from ....core.agent import Agent
from ..schemas import Critique, DebateTurn


class DebateCritic(Agent[DebateTurn, Critique]):
    """Evaluate a single proposal in the context of the full debate record.

    Each turn receives a ``DebateTurn`` (the accumulated
    ``DebateRecord`` plus the specific proposal to focus on) and
    returns a ``Critique`` with a numeric score and comments. Shared
    across every critique round.
    """

    input = DebateTurn
    output = Critique

    role = "You are a rigorous, even-handed debate critic."
    task = (
        "Read the accumulated debate record and focus on the indicated "
        "proposal. Assess its strength — reasoning, evidence, coherence — "
        "in the context of competing proposals and prior critiques. "
        "Return a score in [0.0, 1.0] and concise comments."
    )
    rules = (
        "Judge the focal proposal only; do not re-critique others here.",
        "Score on substance, not style; verbosity does not earn points.",
        "Reference competing proposals only when they directly illuminate the focal one.",
    )
    default_sampling = {"temperature": 0.0}


__all__ = ["DebateCritic"]
