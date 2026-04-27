"""Metric-backed losses."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from operad.metrics.base import Metric, MetricBase
from operad.optim.losses.loss import _clamp01
from operad.optim.parameter import TextualGradient


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _default_gradient_message(
    predicted: BaseModel, expected: BaseModel | None, score: float
) -> str:
    return f"score={score:.3f} for predicted={predicted!r}, expected={expected!r}"


# ---------------------------------------------------------------------------
# Loss.
# ---------------------------------------------------------------------------


class MetricLoss(MetricBase):
    """Lift any `Metric` to a `Loss` by synthesising a gradient string.

    The wrapped metric drives the score; a formatter renders a
    natural-language critique when the score is below `null_threshold`.
    By default `severity = 1.0 - score` (clamped). Override
    `gradient_formatter` to tailor the message, `severity_fn` for
    metrics whose range is not `[0, 1]`.
    """

    def __init__(
        self,
        metric: Metric,
        *,
        gradient_formatter: (
            Callable[[BaseModel, BaseModel | None, float], str] | None
        ) = None,
        severity_fn: Callable[[float], float] | None = None,
        null_threshold: float = 1.0,
        name: str | None = None,
    ) -> None:
        self.metric = metric
        self.name = name if name is not None else metric.name
        self._formatter = gradient_formatter or _default_gradient_message
        self._severity_fn = severity_fn or (lambda s: 1.0 - s)
        self._null_threshold = null_threshold

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        return await self.metric.score(predicted, expected)

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        if expected is None:
            raise ValueError(
                f"{type(self).__name__} wraps a Metric, which requires a "
                "concrete `expected` target; got None"
            )
        s = await self.metric.score(predicted, expected)
        if s >= self._null_threshold:
            return s, TextualGradient.null_gradient()
        msg = self._formatter(predicted, expected, s)
        sev = _clamp01(self._severity_fn(s))
        return s, TextualGradient(message=msg, severity=sev)


__all__ = ["MetricLoss"]
