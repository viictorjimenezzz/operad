"""Regex and substring metrics over a chosen Pydantic field."""

from __future__ import annotations

import re
from dataclasses import dataclass, field as _field
from typing import Any, Literal

from pydantic import BaseModel

from .metric import MetricBase

RegexMode = Literal["contains", "matches", "count"]


@dataclass
class RegexMetric(MetricBase):
    """Deterministic field metric for substring, regex match, and regex count."""

    field: str
    mode: RegexMode
    pattern: str | None = None
    flags: int = 0
    name: str = "regex"
    _compiled: Any = _field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.mode not in ("contains", "matches", "count"):
            raise ValueError(
                "mode must be 'contains', 'matches', or 'count'; "
                f"got {self.mode!r}"
            )
        if self.mode in ("matches", "count") and self.pattern is None:
            raise ValueError(f"mode={self.mode!r} requires pattern")
        if self.name == "regex":
            self.name = f"regex_{self.mode}"

    def _regex(self) -> Any:
        if self.pattern is None:
            raise ValueError(f"mode={self.mode!r} requires pattern")
        if self._compiled is None:
            self._compiled = re.compile(self.pattern, self.flags)
        return self._compiled

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        text = str(getattr(predicted, self.field))
        if self.mode == "contains":
            needle = self.pattern
            if needle is None:
                needle = str(getattr(expected, self.field))
            return 1.0 if needle in text else 0.0
        regex = self._regex()
        if self.mode == "matches":
            return 1.0 if regex.search(text) else 0.0
        return float(len(regex.findall(text)))


__all__ = ["RegexMetric", "RegexMode"]
