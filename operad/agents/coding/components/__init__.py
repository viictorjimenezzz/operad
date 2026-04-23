"""Coding leaves — single-purpose `Agent` building blocks.

Mirrors the shape of ``operad.agents.reasoning.components``: each leaf is
an ``Agent[In, Out]`` with opinionated class-level defaults (``role``,
``task``, ``rules``) and, where useful, one canonical ``Example``.
"""

from __future__ import annotations

from .code_reviewer import CodeReviewer
from .context_optimizer import ContextOptimizer
from .diff_summarizer import DiffSummarizer

__all__ = [
    "CodeReviewer",
    "ContextOptimizer",
    "DiffSummarizer",
]
