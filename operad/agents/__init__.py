"""Reusable agent modules — the `torch.nn` library of operad.

The package is organized by *domain*: each subfolder
(``reasoning/``, future ``coding/``, ``conversational/``, ``memory/``,
...) groups its leaf components under ``components/`` and its composed
multi-agent patterns at the domain root. Structural operators
(``Pipeline``, ``Parallel``) live here at the top level because they
are domain-agnostic.

Common names are re-exported at this level so
``from operad.agents import Reasoner, ReAct, Pipeline`` always works
without users having to know the exact domain path.
"""

from __future__ import annotations

from .coding import (
    CodeReviewer,
    ContextOptimizer,
    DiffChunk,
    DiffSummarizer,
    PRDiff,
    PRReviewer,
    PRSummary,
    ReviewComment,
    ReviewReport,
)
from .parallel import Parallel
from .pipeline import Pipeline
from .reasoning import (
    Action,
    Actor,
    Answer,
    Classifier,
    Critic,
    Evaluator,
    Extractor,
    Observation,
    Planner,
    ReAct,
    Reasoner,
    Task,
    Thought,
)

__all__ = [
    "Action",
    "Actor",
    "Answer",
    "Classifier",
    "CodeReviewer",
    "ContextOptimizer",
    "Critic",
    "DiffChunk",
    "DiffSummarizer",
    "Evaluator",
    "Extractor",
    "Observation",
    "PRDiff",
    "PRReviewer",
    "PRSummary",
    "Parallel",
    "Pipeline",
    "Planner",
    "ReAct",
    "Reasoner",
    "ReviewComment",
    "ReviewReport",
    "Task",
    "Thought",
]
