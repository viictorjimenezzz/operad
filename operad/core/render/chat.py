"""Chat-template-aware renderer.

v1 simply splits the single system string into a messages list so
backends with native chat templates (llama.cpp ``--chat-template``,
Ollama, LM Studio) can see a structured system/user split. Template
detection (ChatML vs. Gemma vs. Mistral) is a follow-up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import xml

if TYPE_CHECKING:
    from ..agent import Agent


def render_system(agent: "Agent[Any, Any]") -> list[dict[str, str]]:
    return [{"role": "system", "content": xml.render_system(agent)}]
