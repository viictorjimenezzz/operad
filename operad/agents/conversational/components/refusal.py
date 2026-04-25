"""Static refusal leaf — no model call, no config required."""

from __future__ import annotations

from ....core.agent import Agent
from ..schemas import SafeguardVerdict, StyledUtterance

_REFUSAL_TEXT = "I can't help with that request."


class RefusalLeaf(Agent[SafeguardVerdict, StyledUtterance]):
    """Return a static refusal response without contacting any model."""

    input = SafeguardVerdict
    output = StyledUtterance

    def __init__(self) -> None:
        super().__init__(config=None, input=SafeguardVerdict, output=StyledUtterance)

    async def forward(self, x: SafeguardVerdict) -> StyledUtterance:  # type: ignore[override]
        return StyledUtterance(response=_REFUSAL_TEXT)
