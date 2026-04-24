"""`Entry[In, Out]` — one row in a benchmark dataset.

`expected_output` is optional (some datasets only have inputs, e.g.
sensitivity analysis or human eval). `metric` is an optional per-row
override the evaluator consults when the caller does not pass a global
metric list.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from ..metrics.base import Metric

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Entry(BaseModel, Generic[In, Out]):
    input: In
    expected_output: Out | None = None
    metric: Metric | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
