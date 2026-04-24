"""Model configuration: which backend, which model, and the sampling knobs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Backend = Literal[
    "llamacpp",
    "lmstudio",
    "ollama",
    "openai",
    "bedrock",
    "anthropic",
    "gemini",
    "huggingface",
]

_LOCAL_BACKENDS: frozenset[Backend] = frozenset(
    {"llamacpp", "lmstudio", "ollama", "huggingface"}
)
_REMOTE_BACKENDS: frozenset[Backend] = frozenset(
    {"openai", "bedrock", "anthropic", "gemini"}
)
_BATCH_BACKENDS: frozenset[Backend] = frozenset(
    {"openai", "anthropic", "bedrock"}
)


class Sampling(BaseModel):
    """LLM sampling knobs."""

    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float | None = None
    top_k: int | None = None
    seed: int | None = None
    stop: list[str] | None = None
    reasoning_tokens: int | None = None

    model_config = ConfigDict(extra="forbid")


class Resilience(BaseModel):
    """Retry / timeout policy."""

    timeout: float | None = None
    max_retries: int = 0
    backoff_base: float = 0.5

    model_config = ConfigDict(extra="forbid")


class IOConfig(BaseModel):
    """Input/output rendering + streaming toggles."""

    stream: bool = False
    structuredio: bool = True
    renderer: Literal["xml", "markdown", "chat"] = "xml"

    model_config = ConfigDict(extra="forbid")


class Runtime(BaseModel):
    """Backend-specific pass-through fields."""

    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class Configuration(BaseModel):
    """Provider-agnostic runtime knobs for a model call.

    `backend` + `model` identify the provider and weights. `host` is required
    for local backends (llamacpp, lmstudio, ollama) and must be absent for
    hosted backends (openai, bedrock, anthropic, gemini). Sampling,
    resilience, io, and backend-specific runtime knobs live in nested
    sub-models.
    """

    backend: Backend
    model: str
    host: str | None = None
    api_key: str | None = None
    batch: bool = False

    sampling: Sampling = Field(default_factory=Sampling)
    resilience: Resilience = Field(default_factory=Resilience)
    io: IOConfig = Field(default_factory=IOConfig)
    runtime: Runtime = Field(default_factory=Runtime)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _check_host_matches_backend(self) -> "Configuration":
        # huggingface runs in-process: no host required, and any host rejected.
        if self.backend == "huggingface":
            if self.host is not None:
                raise ValueError(
                    f"backend={self.backend!r} does not take a `host`; "
                    f"got {self.host!r}"
                )
        elif self.backend in _LOCAL_BACKENDS and not self.host:
            raise ValueError(
                f"backend={self.backend!r} requires `host` "
                f"(e.g. '127.0.0.1:8080')"
            )
        elif self.backend in _REMOTE_BACKENDS and self.host is not None:
            raise ValueError(
                f"backend={self.backend!r} does not take a `host`; "
                f"got {self.host!r}"
            )
        return self

    @model_validator(mode="after")
    def _check_batch_backend(self) -> "Configuration":
        if self.batch and self.backend not in _BATCH_BACKENDS:
            raise ValueError(
                f"batch=True requires backend in {sorted(_BATCH_BACKENDS)!r}; "
                f"got {self.backend!r}"
            )
        return self
