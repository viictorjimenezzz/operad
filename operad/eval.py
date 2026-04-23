"""Dataset-level evaluation: run an agent over (input, expected) pairs.

Minimal harness consumed by `Evolutionary`. Full Stream D will widen the
`Metric` protocol with `score_batch` and ship the scorer catalogue
(`Contains`, `RegexMatch`, `Rouge1`, `RubricCritic`, cost aggregation).
Nothing here pre-empts that: `evaluate` just uses today's `Metric.score`.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

from pydantic import BaseModel

from .core.agent import Agent
from .metrics.base import Metric
from .utils.errors import BuildError

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class EvalReport(BaseModel):
    """Per-row predictions with scores, plus a per-metric summary mean."""

    rows: list[dict[str, Any]]
    summary: dict[str, float]


async def evaluate(
    agent: Agent[In, Out],
    dataset: list[tuple[In, Out]],
    metrics: list[Metric],
    *,
    concurrency: int = 4,
) -> EvalReport:
    """Run `agent` over `dataset`, score each row with every metric.

    The agent must already be built (`agent._built`); we do not silently
    auto-build. Per-row fan-out is bounded by a local
    `asyncio.Semaphore(concurrency)` — this is orthogonal to the slot
    registry, which bounds the backend endpoint rather than the eval
    harness.
    """
    if not agent._built:
        raise BuildError(
            "not_built",
            "call .build() before evaluate()",
            agent=type(agent).__name__,
        )
    if concurrency < 1:
        raise ValueError(f"concurrency must be >= 1, got {concurrency}")

    sem = asyncio.Semaphore(concurrency)

    async def _predict(x: In) -> Out:
        async with sem:
            return await agent(x)

    predictions: list[Out] = await asyncio.gather(
        *(_predict(x) for x, _ in dataset)
    )

    rows: list[dict[str, Any]] = []
    per_metric: dict[str, list[float]] = {m.name: [] for m in metrics}
    for (x, expected), predicted in zip(dataset, predictions):
        row: dict[str, Any] = {
            "input": x.model_dump(mode="json"),
            "expected": expected.model_dump(mode="json"),
            "predicted": predicted.model_dump(mode="json"),
        }
        for m in metrics:
            s = await m.score(predicted, expected)
            row[m.name] = s
            per_metric[m.name].append(s)
        rows.append(row)

    summary: dict[str, float] = {}
    for name, scores in per_metric.items():
        if scores:
            summary[name] = sum(scores) / len(scores)
        else:
            summary[name] = 0.0

    return EvalReport(rows=rows, summary=summary)


__all__ = ["EvalReport", "evaluate"]
