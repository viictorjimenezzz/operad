"""llama.cpp server adapter (HTTP, OpenAI-compatible + llama.cpp extensions)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.config import Configuration
from .params import http_base_url, openai_style_params

if TYPE_CHECKING:
    from strands.models.llamacpp import LlamaCppModel


def build(cfg: Configuration) -> "LlamaCppModel":
    from strands.models.llamacpp import LlamaCppModel

    assert cfg.host is not None
    return LlamaCppModel(
        base_url=http_base_url(cfg.host),
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )
