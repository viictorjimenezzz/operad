"""`Example` — a typed few-shot demonstration pair."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)


class Example(BaseModel, Generic[In, Out]):
    """Typed few-shot demonstration: one `(input, output)` pair."""

    input: In
    output: Out

    model_config = ConfigDict(arbitrary_types_allowed=True)


__all__ = ["Example"]
