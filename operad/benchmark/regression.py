"""`regression_check` — gold-trace replay or dataset evaluation as pass/fail.

Thin façade over `trace_diff` and `evaluate`. Accepts either a gold
`Trace` (trace mode) or a `Dataset` with `expected_output`
(dataset mode) and returns a `RegressionReport` that a CI job can
store as a JSON artefact.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..core.agent import Agent
from ..metrics.base import Metric
from ..runtime.observers import base as _obs
from ..runtime.trace import Trace, TraceObserver, TraceStep
from ..runtime.trace_diff import TraceDiff, trace_diff
from .aggregated import AggregatedMetric, Reducer
from .dataset import Dataset
from .evaluate import EvalReport, evaluate


Equivalence = Literal["exact", "hash", "metric"]


class RegressionReport(BaseModel):
    """Summary of a regression check.

    ``ok`` is the bottom-line pass/fail. ``mode`` is the branch that
    ran. ``trace_diff`` is populated in trace mode, ``eval_report`` in
    dataset mode. ``agent_hash_content`` snapshots the agent identity
    at call time — informational, never used to gate ``ok``.
    """

    ok: bool
    mode: Literal["trace", "dataset"]
    trace_diff: TraceDiff | None = None
    eval_report: EvalReport | None = None
    threshold: float | None = None
    actual: float | None = None
    agent_hash_content: str = ""

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def regression_check(
    agent: Agent[Any, Any],
    gold: Trace | Dataset[Any, Any] | str | Path,
    *,
    metrics: list[Metric] | None = None,
    threshold: float = 1.0,
    reducer: Reducer = "mean",
    equivalence: Equivalence | None = None,
    in_cls: type[BaseModel] | None = None,
    out_cls: type[BaseModel] | None = None,
) -> RegressionReport:
    """Check whether ``agent``'s behaviour has regressed against ``gold``.

    Two branches share one entry point:

    - **Trace mode.** ``gold`` is a previously captured `Trace`; the
      agent is replayed on the same root input and the two traces are
      compared step-by-step. ``equivalence`` selects the strictness:
      ``"exact"`` demands every delta ``"unchanged"``; ``"hash"`` (the
      CI default) tolerates prompt/input hash drift but fails on
      output-schema drift or any response-dump difference;
      ``"metric"`` scores ``prev.response`` vs ``next.response`` per
      step and fails if any score is below ``threshold``.
    - **Dataset mode.** ``gold`` is a `Dataset` with populated
      ``expected_output``; ``evaluate`` runs and each metric's mean
      (or ``reducer``) is computed. ``ok`` iff the pessimistic min
      across metrics meets ``threshold``.

    ``"hash"`` is deterministic and fast — right for CI. ``"metric"``
    is for research where surface variance is tolerable.
    """
    resolved = _resolve_gold(gold, in_cls=in_cls, out_cls=out_cls)

    if isinstance(resolved, Trace):
        return await _trace_mode(
            agent,
            resolved,
            metrics=metrics,
            threshold=threshold,
            equivalence=equivalence or "hash",
        )

    if equivalence is not None:
        raise ValueError(
            f"equivalence={equivalence!r} is trace-only; drop it for "
            "dataset mode"
        )
    if metrics is None or not metrics:
        raise ValueError("dataset mode requires `metrics`")
    return await _dataset_mode(
        agent,
        resolved,
        metrics=metrics,
        threshold=threshold,
        reducer=reducer,
    )


def _resolve_gold(
    gold: Trace | Dataset[Any, Any] | str | Path,
    *,
    in_cls: type[BaseModel] | None,
    out_cls: type[BaseModel] | None,
) -> Trace | Dataset[Any, Any]:
    if isinstance(gold, Trace):
        return gold
    if isinstance(gold, Dataset):
        return gold
    if isinstance(gold, (str, Path)):
        p = Path(gold)
        suffix = p.suffix.lower()
        if suffix in {".ndjson", ".jsonl"}:
            if in_cls is None or out_cls is None:
                raise ValueError(
                    "dataset-path gold requires `in_cls` and `out_cls`"
                )
            return Dataset.load(p, in_cls=in_cls, out_cls=out_cls)
        if suffix == ".json":
            return Trace.load(p)
        raise ValueError(
            f"unrecognised gold path suffix {suffix!r}; expected "
            ".json (trace) or .ndjson/.jsonl (dataset)"
        )
    raise ValueError(
        f"gold must be Trace | Dataset | str | Path, got {type(gold).__name__}"
    )


async def _trace_mode(
    agent: Agent[Any, Any],
    gold: Trace,
    *,
    metrics: list[Metric] | None,
    threshold: float,
    equivalence: Equivalence,
) -> RegressionReport:
    if equivalence == "metric" and (metrics is None or not metrics):
        raise ValueError('equivalence="metric" requires `metrics`')

    next_trace = await _replay(agent, gold)
    diff = trace_diff(gold, next_trace)

    if equivalence == "exact":
        ok = diff.graphs_match and all(
            s.status == "unchanged" for s in diff.steps
        )
        return RegressionReport(
            ok=ok,
            mode="trace",
            trace_diff=diff,
            agent_hash_content=agent.hash_content,
        )

    pairs = _match_steps(gold, next_trace)

    if equivalence == "hash":
        ok = True
        for prev_step, next_step in pairs:
            if prev_step is None or next_step is None:
                ok = False
                continue
            if (
                prev_step.output.hash_output_schema
                != next_step.output.hash_output_schema
            ):
                ok = False
                continue
            if _dump(prev_step) != _dump(next_step):
                ok = False
        return RegressionReport(
            ok=ok,
            mode="trace",
            trace_diff=diff,
            agent_hash_content=agent.hash_content,
        )

    # equivalence == "metric"
    assert metrics is not None
    scored_pairs: list[tuple[TraceStep, TraceStep]] = [
        (a, b) for a, b in pairs if a is not None and b is not None
    ]
    added_or_removed = any(a is None or b is None for a, b in pairs)
    ok = not added_or_removed

    async def _score_pair(
        m: Metric, a: TraceStep, b: TraceStep
    ) -> float:
        return await m.score(b.output.response, a.output.response)

    coros = [
        _score_pair(m, a, b)
        for m in metrics
        for a, b in scored_pairs
    ]
    scores = await asyncio.gather(*coros)
    if any(s < threshold for s in scores):
        ok = False

    return RegressionReport(
        ok=ok,
        mode="trace",
        trace_diff=diff,
        threshold=threshold,
        agent_hash_content=agent.hash_content,
    )


async def _dataset_mode(
    agent: Agent[Any, Any],
    dataset: Dataset[Any, Any],
    *,
    metrics: list[Metric],
    threshold: float,
    reducer: Reducer,
) -> RegressionReport:
    for i, entry in enumerate(dataset):
        if entry.expected_output is None:
            raise ValueError(
                f"dataset entry {i} has no `expected_output` — required "
                "for regression check"
            )

    report = await evaluate(agent, dataset, metrics)
    agg = AggregatedMetric(reducer=reducer)
    per_metric: list[float] = []
    for m in metrics:
        scores = [row[m.name] for row in report.rows if m.name in row]
        per_metric.append(agg.aggregate(scores))
    actual = min(per_metric) if per_metric else float("nan")
    ok = actual >= threshold

    return RegressionReport(
        ok=ok,
        mode="dataset",
        eval_report=report,
        threshold=threshold,
        actual=actual,
        agent_hash_content=agent.hash_content,
    )


async def _replay(agent: Agent[Any, Any], gold: Trace) -> Trace:
    """Replay ``agent`` on ``gold.root_input`` and return its Trace."""
    root_input = agent.input.model_validate(gold.root_input)
    obs = TraceObserver()
    _obs.registry.register(obs)
    try:
        await agent(root_input)
    finally:
        _obs.registry.unregister(obs)
    captured = obs.last()
    if captured is None:
        raise RuntimeError("regression_check: replay produced no trace")
    return captured


def _match_steps(
    prev: Trace, next_: Trace
) -> list[tuple[TraceStep | None, TraceStep | None]]:
    """Pair steps by ``agent_path`` in appearance order.

    Mirrors the pairing used by ``trace_diff``: duplicate paths inside
    one trace (e.g. `BestOfN` fan-out) match sequentially; unmatched
    slots become ``(None, step)`` or ``(step, None)``.
    """
    prev_by_path: dict[str, list[TraceStep]] = defaultdict(list)
    next_by_path: dict[str, list[TraceStep]] = defaultdict(list)
    for s in prev.steps:
        prev_by_path[s.agent_path].append(s)
    for s in next_.steps:
        next_by_path[s.agent_path].append(s)

    seen: set[str] = set()
    ordered: list[str] = []
    for s in next_.steps:
        if s.agent_path not in seen:
            ordered.append(s.agent_path)
            seen.add(s.agent_path)
    for s in prev.steps:
        if s.agent_path not in seen:
            ordered.append(s.agent_path)
            seen.add(s.agent_path)

    pairs: list[tuple[TraceStep | None, TraceStep | None]] = []
    for path in ordered:
        a = prev_by_path.get(path, [])
        b = next_by_path.get(path, [])
        for i in range(max(len(a), len(b))):
            pa = a[i] if i < len(a) else None
            pb = b[i] if i < len(b) else None
            pairs.append((pa, pb))
    return pairs


def _dump(step: TraceStep) -> dict[str, Any]:
    resp = getattr(step.output, "response", None)
    if resp is None:
        return {}
    if isinstance(resp, dict):
        return resp
    dump = getattr(resp, "model_dump", None)
    if dump is None:
        return {}
    try:
        return dump(mode="json")
    except Exception:
        return {}


__all__ = ["RegressionReport", "regression_check"]
