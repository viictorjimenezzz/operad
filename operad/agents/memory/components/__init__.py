"""Memory leaves — single-purpose `Agent` building blocks.

Each component is an ``Agent[Conversation, <T>]`` with opinionated
class-level defaults (``role``, ``task``, ``rules``, ``examples``) and
a pinned input/output contract. Subclass to specialize; instantiate
with ``Cls(config=cfg)`` to use the defaults as-is.
"""

from __future__ import annotations

from .belief_extractor import BeliefExtractor
from .episodic_summarizer import EpisodicSummarizer
from .user_model_extractor import UserModelExtractor

__all__ = [
    "BeliefExtractor",
    "EpisodicSummarizer",
    "UserModelExtractor",
]
