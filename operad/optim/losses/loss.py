"""Loss protocol and composition helpers.

Every `Loss` is also a `Metric` (inherits `MetricBase` to pick up
`score_batch` fan-out), plus an `async compute(predicted, expected) ->
(float, TextualGradient)` that backprop and `Trainer` consume.
"""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from operad.metrics.base import MetricBase
from operad.optim.parameter import TextualGradient


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


# ---------------------------------------------------------------------------
# Protocol.
# ---------------------------------------------------------------------------


@runtime_checkable
class Loss(Protocol):
    """Metric-like object that also returns a structured critique.

    Implementations pair each score with a `TextualGradient` that
    `backward()` propagates through the agent tree. `score == 1.0`
    (or whatever `null_threshold` a concrete loss declares) yields
    `TextualGradient.null_gradient()`, signalling the optimizer to
    skip the affected parameters.
    """

    name: str

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]: ...


# ---------------------------------------------------------------------------
# Composition.
# ---------------------------------------------------------------------------


class CompositeLoss(MetricBase):
    """Weighted combination of sub-losses, evaluated in parallel.

    Weights are normalised so the aggregate score stays in `[0, 1]`
    when each sub-loss does. Sub-gradient messages are concatenated
    in order, `by_field` dicts are merged (later overrides on
    collision), and `target_paths` are concatenated with duplicates
    removed while preserving first-seen order.
    """

    def __init__(
        self,
        losses: list[tuple[Loss, float]],
        *,
        name: str = "composite_loss",
    ) -> None:
        if not losses:
            raise ValueError("CompositeLoss requires at least one sub-loss")
        for _, w in losses:
            if w < 0:
                raise ValueError("CompositeLoss weights must be non-negative")
        total = sum(w for _, w in losses)
        if total <= 0:
            raise ValueError("CompositeLoss weights must sum to > 0")
        self.losses = losses
        self.name = name
        self._norm = [w / total for _, w in losses]

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        scores = await asyncio.gather(
            *(loss.score(predicted, expected) for loss, _ in self.losses)
        )
        return sum(w * s for w, s in zip(self._norm, scores))

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        results = await asyncio.gather(
            *(loss.compute(predicted, expected) for loss, _ in self.losses)
        )
        score_val = sum(w * s for w, (s, _) in zip(self._norm, results))
        severity = sum(w * g.severity for w, (_, g) in zip(self._norm, results))

        messages = [g.message for _, g in results if g.message]
        message = " | ".join(messages)

        by_field: dict[str, str] = {}
        for _, g in results:
            by_field.update(g.by_field)

        seen: set[str] = set()
        target_paths: list[str] = []
        for _, g in results:
            for p in g.target_paths:
                if p not in seen:
                    seen.add(p)
                    target_paths.append(p)

        if severity == 0.0 and not by_field and not message:
            return score_val, TextualGradient.null_gradient()

        return score_val, TextualGradient(
            message=message,
            by_field=by_field,
            severity=_clamp01(severity),
            target_paths=target_paths,
        )


__all__ = [
    "CompositeLoss",
    "Loss",
    "_clamp01",
]
