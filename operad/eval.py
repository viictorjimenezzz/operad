"""Dataset-level evaluation harness.

Runs a built `Agent[In, Out]` over a list of `(In, Out)` pairs, scores
the predictions with one or more `Metric` implementations, and returns
an `EvalReport` with per-row scores and per-metric means.

The harness is intentionally small:
- Does NOT auto-build the agent. Build is a caller responsibility.
- Bounds per-input concurrency with a local `asyncio.Semaphore`; the
  slot registry separately bounds the backend.
- Uses a metric's `score_batch` when present, otherwise loops over
  `score`. This keeps the `Metric` protocol single-method while letting
  LLM-judge metrics like `RubricCritic` fan out with `asyncio.gather`.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from pydantic import BaseModel

from .core.agent import Agent, In, Out
from .metrics.base import Metric
from .utils.errors import BuildError


class EvalReport(BaseModel):
    """Per-row scores + per-metric summary means."""

    rows: list[dict[str, Any]]
    summary: dict[str, float]


async def _score_batch(
    metric: Metric, pairs: list[tuple[BaseModel, BaseModel]]
) -> list[float]:
    if hasattr(metric, "score_batch"):
        return list(await metric.score_batch(pairs))  # type: ignore[attr-defined]
    return [await metric.score(p, e) for p, e in pairs]


async def evaluate(
    agent: Agent[In, Out],
    dataset: list[tuple[In, Out]],
    metrics: list[Metric],
    *,
    concurrency: int = 4,
) -> EvalReport:
    """Evaluate `agent` on `dataset` with `metrics`.

    Raises `BuildError("not_built", ...)` if the agent has not been
    built — the harness will never auto-build.
    """
    if not agent._built:
        raise BuildError(
            "not_built",
            "call .build() before evaluate()",
            agent=type(agent).__name__,
        )

    sem = asyncio.Semaphore(concurrency)

    async def _one(x: In) -> Out:
        async with sem:
            return (await agent(x)).response

    predicted = await asyncio.gather(*(_one(inp) for inp, _ in dataset))
    expected = [exp for _, exp in dataset]
    inputs = [inp for inp, _ in dataset]

    rows: list[dict[str, Any]] = [
        {
            "input": inp.model_dump(mode="json"),
            "expected": exp.model_dump(mode="json"),
            "predicted": pred.model_dump(mode="json"),
        }
        for inp, exp, pred in zip(inputs, expected, predicted)
    ]

    summary: dict[str, float] = {}
    pairs = list(zip(predicted, expected))
    for metric in metrics:
        scores = await _score_batch(metric, pairs)
        for row, s in zip(rows, scores):
            row[metric.name] = s
        valid = [s for s in scores if not math.isnan(s)]
        summary[metric.name] = sum(valid) / len(valid) if valid else float("nan")

    return EvalReport(rows=rows, summary=summary)
