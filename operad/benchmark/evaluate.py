"""Dataset-level evaluation harness.

Runs a built `Agent[In, Out]` over a `Dataset[In, Out]` (or raw
iterable of entries / pairs), scores the predictions with one or more
`Metric` implementations, and returns an `EvalReport` with per-row
scores, per-metric summary means, and reproducibility hashes for the
dataset and graph.

The harness is intentionally small:
- Does NOT auto-build the agent. Build is a caller responsibility.
- Bounds per-input concurrency with a local `asyncio.Semaphore`; the
  slot registry separately bounds the backend.
- Metrics declare `score_batch` via `MetricBase`; LLM-judge metrics
  like `RubricCritic` override it for parallel fan-out.
- `metrics=None` scores each row by its `Entry.metric` (if set).
  Passing an explicit list overrides per-entry policies for every row.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Iterable

from pydantic import BaseModel

from ..core.agent import Agent, In, Out, _compute_graph_hash
from ..metrics.base import Metric
from ..utils.errors import BuildError
from .dataset import Dataset
from .entry import Entry


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
    dataset: Dataset[In, Out] | Iterable[Entry[In, Out]] | Iterable[tuple[In, Out]],
    metrics: list[Metric] | None = None,
    *,
    concurrency: int = 4,
) -> EvalReport:
    """Evaluate ``agent`` on ``dataset``.

    Raises ``BuildError("not_built", ...)`` if the agent has not been
    built — the harness will never auto-build. A raw iterable is
    coerced to an anonymous ``Dataset`` so the hash path is uniform.
    """
    if not agent._built:
        raise BuildError(
            "not_built",
            "call .build() before evaluate()",
            agent=type(agent).__name__,
        )

    ds: Dataset[In, Out] = (
        dataset if isinstance(dataset, Dataset) else Dataset(list(dataset))
    )

    sem = asyncio.Semaphore(concurrency)

    async def _one(x: In) -> Out:
        async with sem:
            return (await agent(x)).response

    entries = list(ds)
    inputs = [e.input for e in entries]
    predicted = await asyncio.gather(*(_one(inp) for inp in inputs))

    rows: list[dict[str, Any]] = []
    for entry, pred in zip(entries, predicted):
        rows.append(
            {
                "input": entry.input.model_dump(mode="json"),
                "expected": (
                    entry.expected_output.model_dump(mode="json")
                    if entry.expected_output is not None
                    else None
                ),
                "predicted": pred.model_dump(mode="json"),
            }
        )

    summary: dict[str, float] = {}

    if metrics is not None:
        pairs: list[tuple[BaseModel, BaseModel | None]] = [
            (pred, entry.expected_output) for entry, pred in zip(entries, predicted)
        ]
        for metric in metrics:
            scores = list(await metric.score_batch(pairs))  # type: ignore[arg-type]
            for row, s in zip(rows, scores):
                row[metric.name] = s
            valid = [s for s in scores if not math.isnan(s)]
            summary[metric.name] = (
                sum(valid) / len(valid) if valid else float("nan")
            )
    else:
        per_metric_scores: dict[str, list[float]] = {}
        for row, entry, pred in zip(rows, entries, predicted):
            if entry.metric is None:
                continue
            score = await entry.metric.score(pred, entry.expected_output)  # type: ignore[arg-type]
            row[entry.metric.name] = score
            row["metric"] = entry.metric.name
            per_metric_scores.setdefault(entry.metric.name, []).append(score)
        for name, scores in per_metric_scores.items():
            valid = [s for s in scores if not math.isnan(s)]
            summary[name] = (
                sum(valid) / len(valid) if valid else float("nan")
            )

    return EvalReport(
        rows=rows,
        summary=summary,
        hash_dataset=ds.hash_dataset,
        hash_graph=_compute_graph_hash(agent),
        dataset_name=ds.name,
        dataset_version=ds.version,
    )
