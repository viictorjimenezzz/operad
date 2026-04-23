"""Replay a stored `Trace` against new metrics — no LLM calls.

Re-scores the recorded root output with caller-supplied metrics.
Zero-cost only for deterministic metrics; metrics that themselves
invoke an LLM (e.g. ``RubricCritic``) still cost. Use
``assert_no_network`` from ``tests/conftest.py`` to enforce that in
tests.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel

from ..eval import EvalReport
from ..metrics.base import Metric
from .trace import Trace


async def replay(
    trace: Trace,
    metrics: list[Metric],
    *,
    expected: BaseModel | None = None,
    predicted_cls: type[BaseModel] | None = None,
    expected_cls: type[BaseModel] | None = None,
) -> EvalReport:
    """Re-score the root output of ``trace`` under ``metrics``.

    ``predicted_cls`` / ``expected_cls`` are used to rehydrate the
    dumped payloads into Pydantic models before scoring. When
    omitted, metrics that accept dicts will still work; those that
    require typed models will raise.
    """
    predicted: Any = trace.root_output
    if predicted_cls is not None:
        predicted = predicted_cls.model_validate(predicted)

    ref: Any = expected
    if expected_cls is not None and expected is not None and not isinstance(expected, BaseModel):
        ref = expected_cls.model_validate(expected)

    row: dict[str, Any] = {
        "run_id": trace.run_id,
        "predicted": predicted
        if not isinstance(predicted, BaseModel)
        else predicted.model_dump(mode="json"),
        "expected": ref.model_dump(mode="json")
        if isinstance(ref, BaseModel)
        else ref,
    }

    summary: dict[str, float] = {}
    for metric in metrics:
        score = await metric.score(predicted, ref)  # type: ignore[arg-type]
        row[metric.name] = score
        summary[metric.name] = score if not math.isnan(score) else float("nan")

    return EvalReport(rows=[row], summary=summary)


__all__ = ["replay"]
