"""LM Studio adapter.

LM Studio exposes an OpenAI-compatible API, so we reuse `OpenAIModel` with
a custom `base_url` pointing at the LM Studio server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.config import Configuration
from .params import http_base_url, openai_style_params

if TYPE_CHECKING:
    from strands.models.openai import OpenAIModel


def build(cfg: Configuration) -> "OpenAIModel":
    from strands.models.openai import OpenAIModel

    assert cfg.host is not None
    base_url = http_base_url(cfg.host)
    # LM Studio's OpenAI-compatible endpoint lives under /v1. Users may pass
    # either the server root or a URL that already includes /v1.
    if not base_url.rstrip("/").endswith("/v1"):
        base_url = f"{base_url}/v1"
    return OpenAIModel(
        client_args={
            "base_url": base_url,
            "api_key": cfg.api_key or "lm-studio",
        },
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )
