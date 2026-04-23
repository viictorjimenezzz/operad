"""Rendering subpackage.

XML is the default renderer (back-compat: ``from operad.core import render``
still exposes ``render_system``, ``render_input``, etc.). Markdown and
chat-template-aware renderers are available as ``render.markdown`` and
``render.chat`` submodules.
"""

from __future__ import annotations

from . import chat, markdown, xml
from .xml import (
    SECTION_DESCRIPTIONS,
    render_examples,
    render_input,
    render_output_schema,
    render_rules,
    render_system,
)

__all__ = [
    "SECTION_DESCRIPTIONS",
    "chat",
    "markdown",
    "render_examples",
    "render_input",
    "render_output_schema",
    "render_rules",
    "render_system",
    "xml",
]
