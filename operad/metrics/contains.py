"""Substring-containment metric over a chosen Pydantic field."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class Contains:
    """1.0 if `str(expected.<field>)` is a substring of `str(predicted.<field>)`.

    Useful for "did the answer mention X?" style evaluation where
    expected is a short phrase and predicted is a longer response.
    """

    field: str
    name: str = "contains"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        needle = str(getattr(expected, self.field))
        haystack = str(getattr(predicted, self.field))
        return 1.0 if needle in haystack else 0.0
