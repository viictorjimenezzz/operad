"""Ollama adapter. Ollama's constructor takes flat kwargs rather than a dict."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.config import Configuration
from .params import http_base_url

if TYPE_CHECKING:
    from strands.models.ollama import OllamaModel


def build(cfg: Configuration) -> "OllamaModel":
    from strands.models.ollama import OllamaModel

    assert cfg.host is not None
    kwargs: dict[str, Any] = {
        "model_id": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if cfg.top_p is not None:
        kwargs["top_p"] = cfg.top_p
    if cfg.stop is not None:
        kwargs["stop_sequences"] = cfg.stop
    if cfg.extra:
        kwargs["options"] = dict(cfg.extra)
    return OllamaModel(host=http_base_url(cfg.host), **kwargs)
