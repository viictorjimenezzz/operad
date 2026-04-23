"""Dataset-level evaluation harness.

Runs a built `Agent[In, Out]` over a `Dataset[In, Out]` (or raw
iterable of pairs), scores the predictions with one or more `Metric`
implementations, and returns an `EvalReport` with per-row scores,
per-metric means, and reproducibility hashes for the dataset and
graph.

The harness is intentionally small:
- Does NOT auto-build the agent. Build is a caller responsibility.
- Bounds per-input concurrency with a local `asyncio.Semaphore`; the
  slot registry separately bounds the backend.
- Metrics declare `score_batch` via `MetricBase`; LLM-judge metrics
  like `RubricCritic` override it for parallel fan-out.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Iterable

from pydantic import BaseModel

from .core.agent import Agent, In, Out, _compute_graph_hash
from .datasets import Dataset
from .metrics.base import Metric
from .utils.errors import BuildError


class EvalReport(BaseModel):
    """Per-row scores + per-metric summary means + reproducibility hashes."""

    rows: list[dict[str, Any]]
    summary: dict[str, float]
    hash_dataset: str = ""
    hash_graph: str = ""
    dataset_name: str = ""
    dataset_version: str = ""


async def evaluate(
    agent: Agent[In, Out],
    dataset: Dataset[In, Out] | Iterable[tuple[In, Out]],
    metrics: list[Metric],
    *,
    concurrency: int = 4,
) -> EvalReport:
    """Evaluate `agent` on `dataset` with `metrics`.

    Raises `BuildError("not_built", ...)` if the agent has not been
    built — the harness will never auto-build. A raw iterable of
    pairs is coerced to an anonymous `Dataset` so the hash path is
    uniform.
    """
    if not agent._built:
        raise BuildError(
            "not_built",
            "call .build() before evaluate()",
            agent=type(agent).__name__,
        )

    ds: Dataset[In, Out] = (
        dataset if isinstance(dataset, Dataset) else Dataset(dataset)
    )

    sem = asyncio.Semaphore(concurrency)

    async def _one(x: In) -> Out:
        async with sem:
            return (await agent(x)).response

    inputs = [inp for inp, _ in ds]
    expected = [exp for _, exp in ds]
    predicted = await asyncio.gather(*(_one(inp) for inp in inputs))

    rows: list[dict[str, Any]] = [
        {
            "input": inp.model_dump(mode="json"),
            "expected": exp.model_dump(mode="json"),
            "predicted": pred.model_dump(mode="json"),
        }
        for inp, exp, pred in zip(inputs, expected, predicted)
    ]

    summary: dict[str, float] = {}
    pairs: list[tuple[BaseModel, BaseModel]] = list(zip(predicted, expected))
    for metric in metrics:
        scores = list(await metric.score_batch(pairs))
        for row, s in zip(rows, scores):
            row[metric.name] = s
        valid = [s for s in scores if not math.isnan(s)]
        summary[metric.name] = sum(valid) / len(valid) if valid else float("nan")

    return EvalReport(
        rows=rows,
        summary=summary,
        hash_dataset=ds.hash_dataset,
        hash_graph=_compute_graph_hash(agent),
        dataset_name=ds.name,
        dataset_version=ds.version,
    )
