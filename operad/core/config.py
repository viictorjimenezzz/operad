"""Model configuration: which backend, which model, and the sampling knobs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Backend = Literal[
    "llamacpp", "lmstudio", "ollama", "openai", "bedrock", "anthropic"
]

_LOCAL_BACKENDS: frozenset[Backend] = frozenset({"llamacpp", "lmstudio", "ollama"})
_REMOTE_BACKENDS: frozenset[Backend] = frozenset(
    {"openai", "bedrock", "anthropic"}
)


class Configuration(BaseModel):
    """Provider-agnostic runtime knobs for a model call.

    `backend` + `model` identify the provider and weights. `host` is required
    for local backends (llamacpp, lmstudio, ollama) and must be absent for
    hosted backends (openai, bedrock). Sampling knobs are backend-agnostic;
    unrecognized provider parameters go into `extra` and are passed through
    by the `models/` resolver.
    """

    backend: Backend
    model: str
    host: str | None = None
    api_key: str | None = None

    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float | None = None
    top_k: int | None = None
    reasoning_tokens: int | None = None
    seed: int | None = None
    stop: list[str] | None = None

    timeout: float | None = None
    max_retries: int = 0
    backoff_base: float = 0.5

    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_host_matches_backend(self) -> "Configuration":
        if self.backend in _LOCAL_BACKENDS and not self.host:
            raise ValueError(
                f"backend={self.backend!r} requires `host` "
                f"(e.g. '127.0.0.1:8080')"
            )
        if self.backend in _REMOTE_BACKENDS and self.host is not None:
            raise ValueError(
                f"backend={self.backend!r} does not take a `host`; "
                f"got {self.host!r}"
            )
        return self
