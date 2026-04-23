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
    Choice,
    Classifier,
    Critic,
    Evaluator,
    Extractor,
    Hit,
    Hits,
    Observation,
    Planner,
    Query,
    ReAct,
    Reasoner,
    Reflection,
    ReflectionInput,
    Reflector,
    Retriever,
    RouteInput,
    Router,
    Switch,
    Task,
    Thought,
    Tool,
    ToolCall,
    ToolResult,
    ToolUser,
)

__all__ = [
    "Action",
    "Actor",
    "Answer",
    "Belief",
    "BeliefExtractor",
    "Beliefs",
    "Choice",
    "Classifier",
    "Conversation",
    "Critic",
    "EpisodicSummarizer",
    "Evaluator",
    "Extractor",
    "Hit",
    "Hits",
    "MemoryStore",
    "Observation",
    "Parallel",
    "Pipeline",
    "Planner",
    "Query",
    "ReAct",
    "Reasoner",
    "Reflection",
    "ReflectionInput",
    "Reflector",
    "Retriever",
    "RouteInput",
    "Router",
    "Summary",
    "Switch",
    "Task",
    "Thought",
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolUser",
    "Turn",
    "UserModel",
    "UserModelExtractor",
]
