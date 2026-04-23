"""Shared helpers for mapping `Configuration` into backend-specific kwargs."""

from __future__ import annotations

from typing import Any

from ..core.config import Configuration


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
