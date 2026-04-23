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
    Reflector,
    Retriever,
    Router,
    Tool,
    ToolUser,
)
from .react import ReAct
from .schemas import (
    Action,
    Answer,
    Choice,
    Hit,
    Hits,
    Observation,
    Query,
    Reflection,
    ReflectionInput,
    RouteInput,
    Task,
    Thought,
    ToolCall,
    ToolResult,
)
from .switch import Switch

__all__ = [
    "Action",
    "Actor",
    "Answer",
    "Choice",
    "Classifier",
    "Critic",
    "Evaluator",
    "Extractor",
    "Hit",
    "Hits",
    "Observation",
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
    "Switch",
    "Task",
    "Thought",
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolUser",
]
