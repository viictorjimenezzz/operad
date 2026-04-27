from __future__ import annotations

"""Retrieval orchestrator leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.rules import (
    RetrievalOrchestratorInput,
    RetrievalOrchestratorOutput,
)


class RetrievalOrchestratorLeaf(
    Agent[RetrievalOrchestratorInput, RetrievalOrchestratorOutput]
):
    """Plans retrieval branches and metadata filters for a search query."""

    input = RetrievalOrchestratorInput
    output = RetrievalOrchestratorOutput
