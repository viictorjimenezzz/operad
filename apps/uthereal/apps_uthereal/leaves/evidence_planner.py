from __future__ import annotations

"""Evidence planner leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.evidence import (
    EvidencePlannerInput,
    EvidencePlannerOutput,
)


class EvidencePlannerLeaf(Agent[EvidencePlannerInput, EvidencePlannerOutput]):
    """Builds claim sequences from retrieved facts and images."""

    input = EvidencePlannerInput
    output = EvidencePlannerOutput
