"""Native Anthropic adapter via `strands.models.anthropic.AnthropicModel`.

Configuration:
    backend="anthropic"
    model="claude-opus-4-7" / "claude-sonnet-4-6" / "claude-haiku-4-5"
    api_key=$ANTHROPIC_API_KEY

`reasoning_tokens` is mapped to Anthropic's extended-thinking budget
(`thinking={"type": "enabled", "budget_tokens": n}`) through
`additional_request_fields`. `cfg.extra` is splatted into the same dict,
so extra Anthropic-specific knobs can be passed there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.config import Configuration

if TYPE_CHECKING:
    from strands.models.anthropic import AnthropicModel


def build(cfg: Configuration) -> "AnthropicModel":
    from strands.models.anthropic import AnthropicModel

    kwargs: dict[str, Any] = {
        "model_id": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if cfg.api_key is not None:
        kwargs["api_key"] = cfg.api_key
    if cfg.top_p is not None:
        kwargs["top_p"] = cfg.top_p
    if cfg.top_k is not None:
        kwargs["top_k"] = cfg.top_k
    if cfg.stop is not None:
        kwargs["stop_sequences"] = cfg.stop
    if cfg.timeout is not None:
        kwargs["timeout"] = cfg.timeout
    if cfg.max_retries:
        kwargs["max_retries"] = cfg.max_retries

    additional: dict[str, Any] = {}
    if cfg.reasoning_tokens is not None:
        additional["thinking"] = {
            "type": "enabled",
            "budget_tokens": cfg.reasoning_tokens,
        }
    additional.update(cfg.extra)
    if additional:
        kwargs["additional_request_fields"] = additional

    return AnthropicModel(**kwargs)
