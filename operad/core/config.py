"""Model configuration: which backend, which model, and the sampling knobs."""

from __future__ import annotations

import logging
import os
import importlib
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic import ValidationError

_logger = logging.getLogger(__name__)

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
# Backends that require an explicit api_key or a fallback env var.
# bedrock is excluded: it authenticates via AWS SDK credentials, not an API key.
_API_KEY_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


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

    API key precedence and env-var fallbacks (checked at construction time):

    - ``openai``: ``api_key`` field, then ``OPENAI_API_KEY`` env var.
    - ``anthropic``: ``api_key`` field, then ``ANTHROPIC_API_KEY`` env var.
    - ``gemini``: ``api_key`` field, then ``GOOGLE_API_KEY`` env var, or
      Vertex AI service-account JSON via ``GOOGLE_VERTEX_AI_SERVICE_ACCOUNT``.
    - ``bedrock``: no API key; uses AWS SDK credential chain (IAM, boto3, etc.).
    - Local backends (llamacpp, lmstudio, ollama, huggingface): no API key required.

    Construction raises ``ValidationError`` when a backend requires a key and
    neither the field nor the env var is present.
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

    @model_validator(mode="after")
    def _check_api_key(self) -> "Configuration":
        if self.backend == "gemini":
            if self.api_key is not None:
                return self
            if os.environ.get("GOOGLE_API_KEY"):
                _logger.debug(
                    "backend=%r: no api_key set, relying on env var %r",
                    self.backend,
                    "GOOGLE_API_KEY",
                )
                return self
            if os.environ.get("GOOGLE_VERTEX_AI_SERVICE_ACCOUNT"):
                _logger.debug(
                    "backend=%r: no api_key set, relying on Vertex service account env",
                    self.backend,
                )
                return self
            raise ValueError(
                "backend='gemini' requires auth; set api_key=, export GOOGLE_API_KEY, "
                "or export GOOGLE_VERTEX_AI_SERVICE_ACCOUNT"
            )

        env_var = _API_KEY_ENV_VARS.get(self.backend)
        if env_var is None:
            return self
        if self.api_key is not None:
            return self
        if os.environ.get(env_var):
            _logger.debug(
                "backend=%r: no api_key set, relying on env var %r",
                self.backend,
                env_var,
            )
            return self
        raise ValueError(
            f"backend={self.backend!r} requires an API key; "
            f"set api_key= or export {env_var}"
        )


class SlotSpec(BaseModel):
    backend: Backend
    host: str | None = None
    limit: int

    model_config = ConfigDict(extra="forbid")


class RuntimeSpec(BaseModel):
    slots: list[SlotSpec] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class OverrideSpec(BaseModel):
    role: str | None = None
    task: str | None = None
    rules: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class RunConfig(BaseModel):
    """Full YAML config: which agent, with what `Configuration` and overrides."""

    agent: str
    config: Configuration
    runtime: RuntimeSpec = Field(default_factory=RuntimeSpec)
    overrides: OverrideSpec = Field(default_factory=OverrideSpec)

    model_config = ConfigDict(extra="forbid")


class ConfigError(Exception):
    """User-facing configuration error (bad file, bad class path, bad schema)."""


def load(path: Path) -> RunConfig:
    """Read a YAML file and validate it into a `RunConfig`."""
    try:
        text = Path(path).read_text()
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {path}") from e
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e}") from e

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {path}: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top-level YAML must be a mapping")

    try:
        return RunConfig.model_validate(data)
    except ValidationError as e:
        raise ConfigError(f"{path}: schema error: {e}") from e


def _import_by_path(dotted: str) -> type[Any]:
    from .agent import Agent

    if "." not in dotted:
        raise ConfigError(
            f"agent must be a fully-qualified path like 'pkg.mod.Class', got {dotted!r}"
        )
    module_path, _, class_name = dotted.rpartition(".")
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise ConfigError(f"cannot import module {module_path!r}: {e}") from e
    try:
        cls = getattr(module, class_name)
    except AttributeError as e:
        raise ConfigError(
            f"module {module_path!r} has no attribute {class_name!r}"
        ) from e
    if not isinstance(cls, type) or not issubclass(cls, Agent):
        raise ConfigError(f"{dotted} is not an Agent subclass")
    return cls


def instantiate(rc: RunConfig) -> Any:
    """Import the configured Agent class and construct an instance.

    Does not call `build()`; callers decide when to build.
    """
    cls = _import_by_path(rc.agent)
    kwargs: dict[str, Any] = {"config": rc.config}
    if rc.overrides.role is not None:
        kwargs["role"] = rc.overrides.role
    if rc.overrides.task is not None:
        kwargs["task"] = rc.overrides.task
    if rc.overrides.rules is not None:
        kwargs["rules"] = rc.overrides.rules
    try:
        return cls(**kwargs)
    except TypeError as e:
        raise ConfigError(f"cannot instantiate {rc.agent}: {e}") from e


def apply_runtime(rc: RunConfig) -> None:
    """Configure per-endpoint concurrency slots from the YAML `runtime` block."""
    from ..runtime.slots import set_limit

    for slot in rc.runtime.slots:
        set_limit(backend=slot.backend, host=slot.host, concurrency=slot.limit)
