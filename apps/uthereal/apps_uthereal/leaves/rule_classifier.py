from __future__ import annotations

"""Rule classifier leaf.

Owner: 2-1-operad-leaves.
"""

from operad import Agent

from apps_uthereal.schemas.rules import RuleClassifierInput, RuleClassifierOutput


class RuleClassifierLeaf(Agent[RuleClassifierInput, RuleClassifierOutput]):
    """Selects tenant rules that match the user's retrieval intent."""

    input = RuleClassifierInput
    output = RuleClassifierOutput
