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
    Choice,
    Classifier,
    Critic,
    Evaluator,
    Extractor,
    Hit,
    Hits,
    Planner,
    Query,
    Reasoner,
    Reflection,
    ReflectionInput,
    Reflector,
    Retriever,
    RouteInput,
    Router,
    Tool,
    ToolCall,
    ToolResult,
    ToolUser,
)
from .react import (
    Action,
    Answer,
    Observation,
    ReAct,
    Task,
    Thought,
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
