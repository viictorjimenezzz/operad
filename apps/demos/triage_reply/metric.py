"""Composite quality metric for the triage_reply demo.

Three signals are combined, each in [0, 1]; the score is their mean.

- ``intent_match``: did the right responder fire? (catches routing errors)
- ``length_ok``:    is the reply text in [80, 320] chars?
- ``warm_close``:   does the reply end with ``?`` or ``!``?

Mirrors `examples/talker_evolution.py::TalkerQualityMetric`'s shape.
"""

from __future__ import annotations

from operad.metrics.base import MetricBase

from schemas import Reply


class TriageReplyMetric(MetricBase):
    name = "triage_reply"

    async def score(self, predicted: Reply, expected: Reply) -> float:
        text = (predicted.text or "").strip()
        if not text:
            return 0.0
        intent_match = float(predicted.intent == expected.intent)
        length_ok = float(80 <= len(text) <= 320)
        warm_close = float(text.endswith(("?", "!")))
        return (intent_match + length_ok + warm_close) / 3.0


__all__ = ["TriageReplyMetric"]
