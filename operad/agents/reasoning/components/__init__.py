"""Reasoning leaves — single-purpose `Agent` building blocks.

Each component is an ``Agent[In, Out]`` with opinionated class-level
defaults (``role``, ``task``, ``rules``). Subclass to pin input/output
types; instantiate with ``Cls(config=cfg, input=I, output=O)`` to use
the defaults ad hoc.
"""

from __future__ import annotations

from .actor import Actor
from .classifier import Classifier
from .critic import Critic
from .evaluator import Evaluator
from .extractor import Extractor
from .planner import Planner
from .reasoner import Reasoner

__all__ = [
    "Actor",
    "Classifier",
    "Critic",
    "Evaluator",
    "Extractor",
    "Planner",
    "Reasoner",
]
