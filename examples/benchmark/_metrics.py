"""Example-local benchmark metrics."""

from __future__ import annotations

from pydantic import BaseModel

from operad.metrics.base import MetricBase


class ToolNameExactMatch(MetricBase):
    """Score only the selected tool name, not its argument JSON."""

    name = "tool_name_exact_match"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        return 1.0 if predicted.tool_name == expected.tool_name else 0.0
