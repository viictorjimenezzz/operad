"""Chat-template-aware renderer.

v1 simply splits the single system string into a messages list so
backends with native chat templates (llama.cpp ``--chat-template``,
Ollama, LM Studio) can see a structured system/user split. Template
detection (ChatML vs. Gemma vs. Mistral) is a follow-up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from . import xml

if TYPE_CHECKING:
    from ..agent import Agent


def render_system(agent: "Agent[Any, Any]") -> list[dict[str, str]]:
    return [{"role": "system", "content": xml.render_system(agent)}]


def render_system_input(x: BaseModel) -> list[dict[str, str]]:
    """Wrap the XML ``<system_input>`` block in a second system message.

    Callers concatenate with :func:`render_system` (the static base) to
    produce the full chat-style prompt for a given call. Returns ``[]``
    when no field carries the system marker.
    """
    content = xml.render_system_input(x)
    if not content:
        return []
    return [{"role": "system", "content": content}]
