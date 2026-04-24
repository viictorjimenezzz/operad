"""Backend resolver: maps a `Configuration` to a concrete `strands.models.Model`.

Every local-first backend has a one-function adapter in this module. The
public entry point is `resolve_model(cfg)`, which dispatches on
`cfg.backend`. Each adapter threads *all* relevant `Configuration` fields
into that backend's native constructor (no silent drops of temperature,
seed, stop, etc.).

Per-backend handling of `Configuration` knobs:

| Backend   | `extra` destination                       | reasoning_tokens       | timeout | max_retries |
| --------- | ----------------------------------------- | ---------------------- | ------- | ----------- |
| llamacpp  | splatted into `params` dict               | max_completion_tokens  | —       | —           |
| lmstudio  | splatted into `params` dict               | max_completion_tokens  | ✓       | ✓           |
| ollama    | wrapped as `options` dict                 | —                      | —       | —           |
| openai    | splatted into `params` dict               | max_completion_tokens  | ✓       | ✓           |
| bedrock   | splatted as top-level BedrockModel kwargs | —                      | —       | —           |
| anthropic | splatted into `additional_request_fields` | thinking.budget_tokens | ✓       | ✓           |

- `extra` semantics match what each backend's native SDK accepts.
- `top_k` and `seed` on bedrock are threaded via `additional_request_fields`;
  other backends put them in their params / kwargs directly.
- `backoff_base` is not consumed by any adapter; it is reserved for
  observer-driven retry logic in `operad.runtime`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import Configuration
from ..utils.errors import BuildError

if TYPE_CHECKING:
    from strands.models.anthropic import AnthropicModel
    from strands.models.bedrock import BedrockModel
    from strands.models.llamacpp import LlamaCppModel
    from strands.models.model import Model
    from strands.models.ollama import OllamaModel
    from strands.models.openai import OpenAIModel


# --- shared parameter helpers ------------------------------------------------


def openai_style_params(cfg: Configuration) -> dict[str, Any]:
    """Build a `params` dict for backends that speak OpenAI-ish sampling keys.

    llama.cpp and LM Studio both accept the OpenAI chat-completions params
    dict (temperature, max_tokens, top_p, seed, stop, ...). llama.cpp also
    accepts its own extensions (top_k, mirostat, grammar, ...), which is
    what `cfg.extra` is for.

    `reasoning_tokens` is forwarded as `max_completion_tokens`, matching
    OpenAI's reasoning-model API; non-reasoning models will error if the
    field is set — callers should leave it unset for those.
    """
    params: dict[str, Any] = {
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
    if cfg.top_p is not None:
        params["top_p"] = cfg.top_p
    if cfg.top_k is not None:
        params["top_k"] = cfg.top_k
    if cfg.seed is not None:
        params["seed"] = cfg.seed
    if cfg.stop is not None:
        params["stop"] = cfg.stop
    if cfg.reasoning_tokens is not None:
        params["max_completion_tokens"] = cfg.reasoning_tokens
    params.update(cfg.extra)
    return params


def openai_client_args(cfg: Configuration) -> dict[str, Any]:
    """Build a `client_args` dict for OpenAI-SDK-backed adapters.

    Threads `timeout` and `max_retries` when set; the OpenAI Python SDK
    accepts both as client constructor kwargs. `api_key` and `base_url`
    are the caller's responsibility.
    """
    args: dict[str, Any] = {}
    if cfg.timeout is not None:
        args["timeout"] = cfg.timeout
    if cfg.max_retries:
        args["max_retries"] = cfg.max_retries
    return args


def http_base_url(host: str) -> str:
    """Turn a `host` like "127.0.0.1:8080" into a full HTTP URL.

    Accepts full URLs verbatim so callers can also pass 'https://...' hosts.
    """
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    return f"http://{host}".rstrip("/")


# --- per-backend constructors (alphabetical) --------------------------------


def _build_anthropic(cfg: Configuration) -> "AnthropicModel":
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


def _build_bedrock(cfg: Configuration) -> "BedrockModel":
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

    additional: dict[str, Any] = {}
    if cfg.top_k is not None:
        additional["top_k"] = cfg.top_k
    if cfg.seed is not None:
        additional["seed"] = cfg.seed
    if additional:
        kwargs["additional_request_fields"] = additional

    kwargs.update(cfg.extra)
    return BedrockModel(**kwargs)


def _build_llamacpp(cfg: Configuration) -> "LlamaCppModel":
    from strands.models.llamacpp import LlamaCppModel

    assert cfg.host is not None
    return LlamaCppModel(
        base_url=http_base_url(cfg.host),
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )


def _build_lmstudio(cfg: Configuration) -> "OpenAIModel":
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


def _build_ollama(cfg: Configuration) -> "OllamaModel":
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


def _build_openai(cfg: Configuration) -> "OpenAIModel":
    from strands.models.openai import OpenAIModel

    client_args: dict[str, Any] = openai_client_args(cfg)
    if cfg.api_key is not None:
        client_args["api_key"] = cfg.api_key
    return OpenAIModel(
        client_args=client_args or None,
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )


# --- resolver ---------------------------------------------------------------


def resolve_model(cfg: Configuration) -> "Model":
    """Return a configured `strands.models.Model` for the given configuration."""
    match cfg.backend:
        case "llamacpp":
            return _build_llamacpp(cfg)
        case "lmstudio":
            return _build_lmstudio(cfg)
        case "ollama":
            return _build_ollama(cfg)
        case "openai":
            return _build_openai(cfg)
        case "bedrock":
            return _build_bedrock(cfg)
        case "anthropic":
            return _build_anthropic(cfg)
        case other:
            raise BuildError(
                "prompt_incomplete",
                f"unknown backend {other!r}",
            )


__all__ = ["resolve_model"]
