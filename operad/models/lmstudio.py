"""LM Studio adapter.

LM Studio exposes an OpenAI-compatible API, so we reuse `OpenAIModel` with
a custom `base_url` pointing at the LM Studio server. When `cfg.api_key`
is unset we pass the literal ``"lm-studio"``; the server accepts any
non-empty key and this keeps the OpenAI SDK's required-key check happy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.config import Configuration
from .params import http_base_url, openai_client_args, openai_style_params

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
    client_args = openai_client_args(cfg)
    client_args["base_url"] = base_url
    client_args["api_key"] = cfg.api_key or "lm-studio"
    return OpenAIModel(
        client_args=client_args,
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )
