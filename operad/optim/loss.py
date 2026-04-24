"""Loss abstractions — `Metric` extended with a `TextualGradient`.

Every `Loss` is also a `Metric` (inherits `MetricBase` to pick up
`score_batch` fan-out), plus an `async compute(predicted, expected) ->
(float, TextualGradient)` that backprop and `Trainer` consume.

A pure `Metric` is not a `Loss`: the runtime-checkable `Loss` Protocol
requires a `compute` attribute, which plain metrics do not have. Lift
them with `LossFromMetric`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from operad.agents.reasoning.schemas import Candidate
from operad.core.agent import Agent
from operad.metrics.base import Metric, MetricBase
from operad.optim.parameter import TextualGradient


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _default_gradient_message(
    predicted: BaseModel, expected: BaseModel | None, score: float
) -> str:
    return f"score={score:.3f} for predicted={predicted!r}, expected={expected!r}"


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


class LossFromMetric(MetricBase):
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


class CriticLoss(MetricBase):
    """Wrap an `Agent[Candidate, Score-like]` (an LLM judge) as a loss.

    The critic's output is duck-typed on `.score` and `.rationale`, so
    any Pydantic model with those attributes works — `Score` itself
    from `operad.agents.reasoning.schemas`, or a user-defined subclass
    that adds richer fields.
    """

    def __init__(
        self,
        critic: Agent[Any, Any],
        *,
        name: str = "critic_loss",
        severity_from: Literal["score", "rationale"] = "score",
        null_threshold: float = 1.0,
    ) -> None:
        self.critic = critic
        self.name = name
        self._severity_from = severity_from
        self._null_threshold = null_threshold

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        out = await self.critic(Candidate(output=predicted))
        return float(out.response.score)

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        del expected
        out = await self.critic(Candidate(output=predicted))
        resp = out.response
        s = float(resp.score)
        if s >= self._null_threshold:
            return s, TextualGradient.null_gradient()
        message = str(getattr(resp, "rationale", ""))
        if self._severity_from == "score":
            sev = _clamp01(1.0 - s)
        else:
            sev = 1.0
        return s, TextualGradient(message=message, severity=sev)


class JSONShapeLoss(MetricBase):
    """Pure schema-shape loss: does `predicted` satisfy `schema`?

    `expected` is ignored. Useful when the only requirement is "the
    answer parses as the target schema." Score is the fraction of
    required fields that validate; per-field diagnostics populate
    `by_field` on the gradient.
    """

    def __init__(
        self, schema: type[BaseModel], *, name: str = "json_shape"
    ) -> None:
        self.schema = schema
        self.name = name

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        s, _ = await self.compute(predicted, None)
        return s

    async def compute(
        self, predicted: BaseModel, expected: BaseModel | None
    ) -> tuple[float, TextualGradient]:
        del expected
        required = [
            n for n, f in self.schema.model_fields.items() if f.is_required()
        ]
        by_field: dict[str, str] = {}
        data = predicted.model_dump()
        try:
            self.schema.model_validate(data)
        except ValidationError as ve:
            for err in ve.errors():
                loc = err.get("loc", ())
                key = str(loc[0]) if loc else "?"
                by_field[key] = err.get("msg", "validation error")

        if not by_field:
            return 1.0, TextualGradient.null_gradient()

        total = max(1, len(required))
        bad_required = sum(1 for k in by_field if k in required)
        score_val = _clamp01((total - bad_required) / total)
        message = "; ".join(f"{k}: {v}" for k, v in by_field.items())
        return score_val, TextualGradient(
            message=message, by_field=by_field, severity=_clamp01(1.0 - score_val)
        )


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
    "CriticLoss",
    "JSONShapeLoss",
    "Loss",
    "LossFromMetric",
]
