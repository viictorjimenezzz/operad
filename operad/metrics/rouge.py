"""Rouge-1 (unigram overlap) F1 metric — pure Python, no dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel

from .base import MetricBase

_TOKEN = re.compile(r"\w+")


def _tokens(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


@dataclass
class Rouge1(MetricBase):
    """Unigram overlap F1 between `predicted.<field>` and `expected.<field>`.

    Not a full `rouge-score` reimplementation — just precision, recall,
    and F1 over lowercased word tokens. Returns F1 (higher is better).
    0.0 if either side is empty.
    """

    field: str
    name: str = "rouge1"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pred = _tokens(str(getattr(predicted, self.field)))
        ref = _tokens(str(getattr(expected, self.field)))
        if not pred or not ref:
            return 0.0
        pred_set = set(pred)
        ref_set = set(ref)
        overlap = len(pred_set & ref_set)
        if overlap == 0:
            return 0.0
        precision = overlap / len(pred_set)
        recall = overlap / len(ref_set)
        return 2 * precision * recall / (precision + recall)
