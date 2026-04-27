from __future__ import annotations

"""Fact filter leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.evidence import FactFilterInput, FactFilterOutput


class FactFilterLeaf(Agent[FactFilterInput, FactFilterOutput]):
    """Filters retrieved facts down to evidence relevant to the query."""

    input = FactFilterInput
    output = FactFilterOutput
