"""Reasoning domain: leaf components + composed reasoning patterns.

This is the first ``agents/<domain>/`` folder and the template for the
rest: each domain groups its leaves under ``components/`` and puts
composed multi-agent patterns at the domain root. Future domains
(``coding``, ``conversational``, ``memory``, ...) will follow the same
shape.
"""

from __future__ import annotations

from .components import (
    Actor,
    Classifier,
    Critic,
    Evaluator,
    Extractor,
    Planner,
    Reasoner,
)
from .react import (
    Action,
    Answer,
    Observation,
    ReAct,
    Task,
    Thought,
)

__all__ = [
    "Action",
    "Actor",
    "Answer",
    "Classifier",
    "Critic",
    "Evaluator",
    "Extractor",
    "Observation",
    "Planner",
    "ReAct",
    "Reasoner",
    "Task",
    "Thought",
]
