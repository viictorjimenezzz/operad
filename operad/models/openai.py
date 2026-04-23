"""OpenAI adapter (hosted api.openai.com)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.config import Configuration
from .params import openai_client_args, openai_style_params

if TYPE_CHECKING:
    from strands.models.openai import OpenAIModel


def build(cfg: Configuration) -> "OpenAIModel":
    from strands.models.openai import OpenAIModel

    client_args: dict[str, Any] = openai_client_args(cfg)
    if cfg.api_key is not None:
        client_args["api_key"] = cfg.api_key
    return OpenAIModel(
        client_args=client_args or None,
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )
