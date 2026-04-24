"""Rank Agent configuration parameters by how much each moves a metric.

``sensitivity(agent, dataset, metric)`` evaluates the agent on ``dataset``
once to get a baseline aggregate score, then re-evaluates one clone per
``(parameter-path, value)`` perturbation and reports which paths produce
the largest absolute deltas from baseline.

Design note: we intentionally do NOT delegate to ``operad.algorithms.Sweep``
here. Sweep's public API is ``run(x: In) -> SweepReport`` — it runs each
clone against a single input, not over a dataset — and it exposes no
"build clones only" intermediate step. We rebuild the clone + build step
locally using the same public primitives Sweep uses (``Agent.clone``,
``set_path``, ``abuild``).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from ..core.agent import Agent
from ..metrics.base import Metric
from ..utils.paths import set_path
from .aggregated import AggregatedMetric, Reducer
from .dataset import Dataset
from .evaluate import evaluate


class SensitivityCell(BaseModel):
    """One (parameter-path, value) assignment and its aggregated metric."""

    parameter: str
    value: Any
    score: float


class SensitivityReport(BaseModel):
    """Baseline score, per-cell results, and per-path ranking by |delta|."""

    baseline: float
    cells: list[SensitivityCell] = Field(default_factory=list)
    ranking: list[tuple[str, float]] = Field(default_factory=list)


async def sensitivity(
    agent: Agent,
    dataset: Dataset,
    metric: Metric,
    *,
    perturbations: dict[str, list[Any]] | None = None,
    reducer: Reducer = "mean",
    concurrency: int = 4,
    max_combinations: int = 1024,
) -> SensitivityReport:
    """Rank configuration parameters by the metric shift they induce.

    The agent must be built. ``perturbations`` maps dotted attribute paths
    (e.g. ``"config.sampling.temperature"``) to absolute values to try. If omitted,
    a default set probes common sampling knobs derived from the agent's
    current configuration.

    Cost: ``sum(len(values) for values in perturbations.values()) + 1``
    dataset evaluations, each costing ``len(dataset)`` forwards. Cap via
    ``max_combinations`` (applied to total perturbation cells, excluding
    the baseline).
    """
    if concurrency < 1:
        raise ValueError(f"concurrency must be >= 1, got {concurrency}")
    if max_combinations < 1:
        raise ValueError(
            f"max_combinations must be >= 1, got {max_combinations}"
        )

    resolved = (
        _default_perturbations(agent) if perturbations is None else perturbations
    )

    total = sum(len(values) for values in resolved.values())
    if total > max_combinations:
        raise ValueError(
            f"sensitivity would produce {total} perturbation cells, "
            f"exceeding max_combinations={max_combinations}; tighten the "
            f"perturbation set or raise the cap"
        )

    aggregator = AggregatedMetric(reducer=reducer, name=metric.name)
    baseline = await _evaluate_aggregate(agent, dataset, metric, aggregator)

    tasks: list[tuple[str, Any]] = [
        (path, value) for path, values in resolved.items() for value in values
    ]
    if not tasks:
        return SensitivityReport(baseline=baseline, cells=[], ranking=[])

    sem = asyncio.Semaphore(concurrency)

    async def _one(path: str, value: Any) -> SensitivityCell:
        async with sem:
            score = await _score_perturbation(
                agent, dataset, metric, aggregator, path, value
            )
            return SensitivityCell(parameter=path, value=value, score=score)

    cells = list(
        await asyncio.gather(*(_one(path, value) for path, value in tasks))
    )

    by_path: dict[str, list[float]] = {}
    for cell in cells:
        by_path.setdefault(cell.parameter, []).append(
            abs(cell.score - baseline)
        )
    ranking = sorted(
        ((path, max(deltas)) for path, deltas in by_path.items()),
        key=lambda item: (-item[1], item[0]),
    )

    return SensitivityReport(baseline=baseline, cells=cells, ranking=ranking)


async def _evaluate_aggregate(
    agent: Agent,
    dataset: Dataset,
    metric: Metric,
    aggregator: AggregatedMetric,
) -> float:
    report = await evaluate(agent, dataset, [metric], concurrency=1)
    scores = [float(row[metric.name]) for row in report.rows]
    return aggregator.aggregate(scores)


async def _score_perturbation(
    agent: Agent,
    dataset: Dataset,
    metric: Metric,
    aggregator: AggregatedMetric,
    path: str,
    value: Any,
) -> float:
    clone = agent.clone()
    try:
        set_path(clone, path, value)
    except KeyError as e:
        raise ValueError(
            f"sensitivity: invalid perturbation path {path!r}: {e}"
        ) from e
    await clone.abuild()
    return await _evaluate_aggregate(clone, dataset, metric, aggregator)


def _default_perturbations(agent: Agent) -> dict[str, list[Any]]:
    """Probe sampling knobs around the agent's current configuration.

    Skips an axis when the current value is ``None`` rather than inventing
    a baseline. Raises ``ValueError`` if no axis applies.
    """
    config = getattr(agent, "config", None)
    if config is None:
        raise ValueError(
            "sensitivity: agent has no config; provide explicit perturbations"
        )

    result: dict[str, list[Any]] = {}

    sampling = getattr(config, "sampling", None)
    if sampling is None:
        raise ValueError(
            "sensitivity: agent.config has no sampling block; provide "
            "explicit perturbations"
        )

    temperature = getattr(sampling, "temperature", None)
    if temperature is not None:
        candidates = [
            round(max(0.0, min(2.0, temperature - 0.2)), 4),
            round(max(0.0, min(2.0, temperature + 0.2)), 4),
        ]
        values = _dedup_excluding(candidates, temperature)
        if values:
            result["config.sampling.temperature"] = values

    top_p = getattr(sampling, "top_p", None)
    if top_p is not None:
        candidates = [
            round(max(0.01, min(1.0, top_p - 0.1)), 4),
            round(max(0.01, min(1.0, top_p + 0.1)), 4),
        ]
        values = _dedup_excluding(candidates, top_p)
        if values:
            result["config.sampling.top_p"] = values

    top_k = getattr(sampling, "top_k", None)
    if top_k is not None:
        candidates = [max(1, top_k - 10), top_k + 10]
        values = _dedup_excluding(candidates, top_k)
        if values:
            result["config.sampling.top_k"] = values

    max_tokens = getattr(sampling, "max_tokens", None)
    if max_tokens is not None:
        candidates = [max(1, max_tokens - 256), max_tokens + 256]
        values = _dedup_excluding(candidates, max_tokens)
        if values:
            result["config.sampling.max_tokens"] = values

    if not result:
        raise ValueError(
            "sensitivity: no default perturbations applicable to this "
            "agent's config; provide explicit perturbations"
        )
    return result


def _dedup_excluding(candidates: list[Any], baseline: Any) -> list[Any]:
    seen: set[Any] = set()
    out: list[Any] = []
    for value in candidates:
        if value == baseline or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
