"""AWS Bedrock adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.config import Configuration

if TYPE_CHECKING:
    from strands.models.bedrock import BedrockModel


def build(cfg: Configuration) -> "BedrockModel":
    from strands.models.bedrock import BedrockModel

    kwargs: dict[str, Any] = {
        "model_id": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if cfg.top_p is not None:
        kwargs["top_p"] = cfg.top_p
    if cfg.stop is not None:
        kwargs["stop_sequences"] = cfg.stop
    kwargs.update(cfg.extra)
    return BedrockModel(**kwargs)
