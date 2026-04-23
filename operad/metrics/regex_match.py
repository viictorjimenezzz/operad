"""Regex-match metric over a chosen Pydantic field."""

from __future__ import annotations

import re
from dataclasses import dataclass, field as _field
from typing import Any

from pydantic import BaseModel


@dataclass
class RegexMatch:
    """1.0 if `pattern` matches the string form of `predicted.<field>`.

    Uses `re.search` (partial match). The pattern is compiled once on
    first use and cached on the instance.
    """

    field: str
    pattern: str
    name: str = "regex_match"
    _compiled: Any = _field(default=None, init=False, repr=False, compare=False)

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        del expected
        if self._compiled is None:
            self._compiled = re.compile(self.pattern)
        text = str(getattr(predicted, self.field))
        return 1.0 if self._compiled.search(text) else 0.0
