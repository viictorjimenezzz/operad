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

from .conversational import (
    Persona,
    RefusalLeaf,
    Safeguard,
    SafeguardVerdict,
    StyledUtterance,
    Talker,
    TurnChoice,
    TurnTaker,
    Utterance,
)
from .memory import (
    Belief,
    BeliefExtractor,
    Beliefs,
    Conversation,
    EpisodicSummarizer,
    MemoryStore,
    Summary,
    Turn,
    UserModel,
    UserModelExtractor,
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
    "Belief",
    "BeliefExtractor",
    "Beliefs",
    "Classifier",
    "Conversation",
    "Critic",
    "EpisodicSummarizer",
    "Evaluator",
    "Extractor",
    "MemoryStore",
    "Observation",
    "Parallel",
    "Persona",
    "Pipeline",
    "Planner",
    "ReAct",
    "Reasoner",
    "RefusalLeaf",
    "Safeguard",
    "SafeguardVerdict",
    "StyledUtterance",
    "Summary",
    "Talker",
    "Task",
    "Thought",
    "Turn",
    "TurnChoice",
    "TurnTaker",
    "UserModel",
    "UserModelExtractor",
    "Utterance",
]
