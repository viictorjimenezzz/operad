"""Reasoning leaves — single-purpose `Agent` building blocks.

Each component is an ``Agent[In, Out]`` with opinionated class-level
defaults (``role``, ``task``, ``rules``). Subclass to pin input/output
types; instantiate with ``Cls(config=cfg, input=I, output=O)`` to use
the defaults ad hoc.
"""

from __future__ import annotations

from .actor import Actor
from .bm25_retriever import BM25Retriever
from .chat_reasoner import ChatReasoner
from .classifier import Classifier
from .decontextualizer import Decontextualizer
from .critic import Critic
from .evaluator import Evaluator
from .extractor import Extractor
from .fake_retriever import FakeRetriever
from .planner import Planner
from .reasoner import Reasoner
from .reformulator import Reformulator
from .reflector import Reflection, ReflectionInput, Reflector
from .retriever import Hit, Hits, Query, Retriever
from .router import Choice, RouteInput, Router
from .summarizer import Summarizer
from .tool_user import Tool, ToolCall, ToolResult, ToolUser

__all__ = [
    "Actor",
    "BM25Retriever",
    "ChatReasoner",
    "Choice",
    "Classifier",
    "Decontextualizer",
    "Critic",
    "Evaluator",
    "Extractor",
    "FakeRetriever",
    "Hit",
    "Hits",
    "Planner",
    "Query",
    "Reformulator",
    "Reasoner",
    "Reflection",
    "ReflectionInput",
    "Reflector",
    "Retriever",
    "RouteInput",
    "Router",
    "Summarizer",
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolUser",
]
