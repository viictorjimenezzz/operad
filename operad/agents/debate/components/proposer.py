"""Proposer leaf: generates one opinionated answer to a debate topic."""

from __future__ import annotations

from ...reasoning.components.reasoner import Reasoner
from ..schemas import DebateContext, Proposal


class Proposer(Reasoner):
    """Generate a single concrete proposal for a ``DebateContext``.

    Used by ``Debate`` as one of N proposers. Each clone sees the same
    topic but is expected (via sampling variance or seeded configs) to
    produce a distinct angle. Subclass to specialize role or rules for
    a domain-specific debate.
    """

    input = DebateContext
    output = Proposal

    role = "You are an opinionated proposer in a structured debate."
    task = (
        "Read the debate topic and produce one concrete, defensible "
        "proposal. State a position and justify it briefly; do not "
        "hedge into neutrality."
    )
    rules = (
        "Commit to a specific stance; avoid 'on the one hand / on the other hand' framing.",
        "Keep the proposal focused — one position per turn.",
        "Ground claims in reasoning; unsupported assertions weaken the debate.",
    )
    default_sampling = {"temperature": 0.9}


__all__ = ["Proposer"]
