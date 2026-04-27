"""Judge-backed losses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from operad.agents.reasoning.schemas import Candidate
from operad.core.agent import Agent
from operad.metrics.metric import MetricBase
from operad.optim.losses.loss import _clamp01
from operad.optim.parameter import TextualGradient


# ---------------------------------------------------------------------------
# Loss.
# ---------------------------------------------------------------------------


class LLMAAJ(MetricBase):
    """Wrap an `Agent[Candidate, Score-like]` judge as a loss.

    The judge's output is duck-typed on `.score` and `.rationale`, so
    any Pydantic model with those attributes works: `Score` from
    `operad.agents.reasoning.schemas`, or a user-defined subclass that
    adds richer fields.
    """

    def __init__(
        self,
        judge: Agent[Any, Any],
        *,
        name: str = "judge_loss",
        severity_from: Literal["score", "rationale"] = "score",
        null_threshold: float = 1.0,
    ) -> None:
        self.judge = judge
        self.name = name
        self._severity_from = severity_from
        self._null_threshold = null_threshold

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        out = await self.judge(Candidate(output=predicted))
        return float(out.response.score)

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        del expected
        out = await self.judge(Candidate(output=predicted))
        resp = out.response
        s = float(resp.score)
        if s >= self._null_threshold:
            return s, TextualGradient.null_gradient()
        message = str(getattr(resp, "rationale", ""))
        sev = _clamp01(1.0 - s) if self._severity_from == "score" else 1.0
        return s, TextualGradient(message=message, severity=sev)


__all__ = ["LLMAAJ"]
