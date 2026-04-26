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
    BM25Retriever,
    ChatReasoner,
    Classifier,
    Decontextualizer,
    Critic,
    Evaluator,
    Extractor,
    FakeRetriever,
    Planner,
    Reasoner,
    Reformulator,
    Reflector,
    Retriever,
    Router,
    Summarizer,
    Tool,
    ToolUser,
)
from .debate import DebateAgent
from .react import ReAct
from .schemas import (
    Action,
    Answer,
    ChatReasonerInput,
    ChatReasonerOutput,
    ChatRoute,
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
from .verifier import VerifierAgent

__all__ = [
    "Action",
    "Actor",
    "DebateAgent",
    "Answer",
    "BM25Retriever",
    "ChatReasoner",
    "ChatReasonerInput",
    "ChatReasonerOutput",
    "ChatRoute",
    "Choice",
    "Classifier",
    "Decontextualizer",
    "Critic",
    "Evaluator",
    "Extractor",
    "FakeRetriever",
    "Hit",
    "Hits",
    "Observation",
    "Planner",
    "Query",
    "ReAct",
    "Reformulator",
    "Reasoner",
    "Reflection",
    "ReflectionInput",
    "Reflector",
    "Retriever",
    "RouteInput",
    "Router",
    "Summarizer",
    "Switch",
    "Task",
    "Thought",
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolUser",
    "VerifierAgent",
]
