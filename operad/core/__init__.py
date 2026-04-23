"""Foundations: Agent, Example, Configuration, build, graph export.

`from operad.core import ...` or (more commonly) `from operad import ...`
are both valid. The top-level ``operad`` package re-exports again for
the flattest possible call site.
"""

from __future__ import annotations

from .agent import Agent, Example, In, Out
from .build import AgentGraph, Edge, Node, abuild_agent, build_agent
from .config import Backend, Configuration
from .diff import AgentDiff, Change
from .graph import to_json, to_mermaid
from .output import OperadOutput
from .state import AgentState

__all__ = [
    "Agent",
    "AgentDiff",
    "AgentGraph",
    "AgentState",
    "Backend",
    "Change",
    "Configuration",
    "Edge",
    "Example",
    "In",
    "Node",
    "OperadOutput",
    "Out",
    "abuild_agent",
    "build_agent",
    "to_json",
    "to_mermaid",
]
