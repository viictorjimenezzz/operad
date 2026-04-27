from __future__ import annotations

"""Reasoner leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.reasoner import ReasonerInput, ReasonerOutput


class ReasonerLeaf(Agent[ReasonerInput, ReasonerOutput]):
    """Rewrites the user message and selects direct answer or RAG routing."""

    input = ReasonerInput
    output = ReasonerOutput
