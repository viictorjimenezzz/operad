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

import json
import os
import time
import warnings
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from .config import Backend, Configuration
from ..utils.errors import BuildError

if TYPE_CHECKING:
    from strands.models.anthropic import AnthropicModel
    from strands.models.bedrock import BedrockModel
    from strands.models.gemini import GeminiModel
    from strands.models.llamacpp import LlamaCppModel
    from strands.models.model import Model
    from strands.models.ollama import OllamaModel
    from strands.models.openai import OpenAIModel


class BatchHandle(BaseModel):
    """Opaque handle to a provider-side batch submission."""

    provider: Backend
    provider_batch_id: str
    endpoint: str
    submitted_at: float
    raw: dict[str, Any] = Field(default_factory=dict)


class BatchResult(BaseModel):
    """Terminal state for a batch job: completion, failure, or cancellation."""

    handle: BatchHandle
    status: Literal["completed", "failed", "cancelled"]
    output: Any = None
    error: str | None = None


# --- shared parameter helpers ------------------------------------------------


def openai_style_params(cfg: Configuration) -> dict[str, Any]:
    """Build a `params` dict for backends that speak OpenAI-ish sampling keys.

    llama.cpp and LM Studio both accept the OpenAI chat-completions params
    dict (temperature, max_tokens, top_p, seed, stop, ...). llama.cpp also
    accepts its own extensions (top_k, mirostat, grammar, ...), which is
    what `cfg.runtime.extra` is for.

    `reasoning_tokens` is forwarded as `max_completion_tokens`, matching
    OpenAI's reasoning-model API; non-reasoning models will error if the
    field is set — callers should leave it unset for those.
    """
    params: dict[str, Any] = {
        "temperature": cfg.sampling.temperature,
        "max_tokens": cfg.sampling.max_tokens,
    }
    if cfg.sampling.top_p is not None:
        params["top_p"] = cfg.sampling.top_p
    if cfg.sampling.top_k is not None:
        params["top_k"] = cfg.sampling.top_k
    if cfg.sampling.seed is not None:
        params["seed"] = cfg.sampling.seed
    if cfg.sampling.stop is not None:
        params["stop"] = cfg.sampling.stop
    if cfg.sampling.reasoning_tokens is not None:
        params["max_completion_tokens"] = cfg.sampling.reasoning_tokens
    params.update(cfg.runtime.extra)
    return params


def openai_client_args(cfg: Configuration) -> dict[str, Any]:
    """Build a `client_args` dict for OpenAI-SDK-backed adapters.

    Threads `timeout` and `max_retries` when set; the OpenAI Python SDK
    accepts both as client constructor kwargs. `api_key` and `base_url`
    are the caller's responsibility.
    """
    args: dict[str, Any] = {}
    if cfg.resilience.timeout is not None:
        args["timeout"] = cfg.resilience.timeout
    if cfg.resilience.max_retries:
        args["max_retries"] = cfg.resilience.max_retries
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
        "temperature": cfg.sampling.temperature,
        "max_tokens": cfg.sampling.max_tokens,
    }
    if cfg.api_key is not None:
        kwargs["api_key"] = cfg.api_key
    if cfg.sampling.top_p is not None:
        kwargs["top_p"] = cfg.sampling.top_p
    if cfg.sampling.top_k is not None:
        kwargs["top_k"] = cfg.sampling.top_k
    if cfg.sampling.stop is not None:
        kwargs["stop_sequences"] = cfg.sampling.stop
    if cfg.resilience.timeout is not None:
        kwargs["timeout"] = cfg.resilience.timeout
    if cfg.resilience.max_retries:
        kwargs["max_retries"] = cfg.resilience.max_retries

    additional: dict[str, Any] = {}
    if cfg.sampling.reasoning_tokens is not None:
        additional["thinking"] = {
            "type": "enabled",
            "budget_tokens": cfg.sampling.reasoning_tokens,
        }
    additional.update(cfg.runtime.extra)
    if additional:
        kwargs["additional_request_fields"] = additional

    return AnthropicModel(**kwargs)


def _build_bedrock(cfg: Configuration) -> "BedrockModel":
    from strands.models.bedrock import BedrockModel

    kwargs: dict[str, Any] = {
        "model_id": cfg.model,
        "temperature": cfg.sampling.temperature,
        "max_tokens": cfg.sampling.max_tokens,
    }
    if cfg.sampling.top_p is not None:
        kwargs["top_p"] = cfg.sampling.top_p
    if cfg.sampling.stop is not None:
        kwargs["stop_sequences"] = cfg.sampling.stop

    additional: dict[str, Any] = {}
    if cfg.sampling.top_k is not None:
        additional["top_k"] = cfg.sampling.top_k
    if cfg.sampling.seed is not None:
        additional["seed"] = cfg.sampling.seed
    if additional:
        kwargs["additional_request_fields"] = additional

    kwargs.update(cfg.runtime.extra)
    return BedrockModel(**kwargs)


def _build_llamacpp(cfg: Configuration) -> "LlamaCppModel":
    from strands.models.llamacpp import LlamaCppModel

    if cfg.host is None:
        raise BuildError("prompt_incomplete", f"backend={cfg.backend!r} requires host")
    return LlamaCppModel(
        base_url=http_base_url(cfg.host),
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )


def _build_lmstudio(cfg: Configuration) -> "OpenAIModel":
    from strands.models.openai import OpenAIModel

    if cfg.host is None:
        raise BuildError("prompt_incomplete", f"backend={cfg.backend!r} requires host")
    base_url = http_base_url(cfg.host)
    # LM Studio's OpenAI-compatible endpoint lives under /v1. Users may pass
    # either the server root or a URL that already includes /v1.
    if not base_url.rstrip("/").endswith("/v1"):
        base_url = f"{base_url}/v1"
    client_args = openai_client_args(cfg)
    client_args["base_url"] = base_url
    if cfg.api_key is None:
        import logging as _logging
        _logging.getLogger(__name__).debug(
            "backend='lmstudio': no api_key set, using placeholder 'lm-studio'"
        )
    client_args["api_key"] = cfg.api_key or "lm-studio"
    return OpenAIModel(
        client_args=client_args,
        model_id=cfg.model,
        params=openai_style_params(cfg),
    )


def _build_ollama(cfg: Configuration) -> "OllamaModel":
    from strands.models.ollama import OllamaModel

    if cfg.host is None:
        raise BuildError("prompt_incomplete", f"backend={cfg.backend!r} requires host")
    kwargs: dict[str, Any] = {
        "model_id": cfg.model,
        "temperature": cfg.sampling.temperature,
        "max_tokens": cfg.sampling.max_tokens,
    }
    if cfg.sampling.top_p is not None:
        kwargs["top_p"] = cfg.sampling.top_p
    if cfg.sampling.stop is not None:
        kwargs["stop_sequences"] = cfg.sampling.stop
    if cfg.runtime.extra:
        kwargs["options"] = dict(cfg.runtime.extra)
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


def _build_gemini(cfg: Configuration) -> "GeminiModel":
    try:
        from strands.models.gemini import GeminiModel
    except ImportError as e:
        raise ImportError(
            "Gemini backend requires the [gemini] extra: "
            "`pip install 'operad[gemini]'`."
        ) from e

    params: dict[str, Any] = {
        "temperature": cfg.sampling.temperature,
        "max_output_tokens": cfg.sampling.max_tokens,
    }
    if cfg.sampling.top_p is not None:
        params["top_p"] = cfg.sampling.top_p
    if cfg.sampling.top_k is not None:
        params["top_k"] = cfg.sampling.top_k
    if cfg.sampling.seed is not None:
        params["seed"] = cfg.sampling.seed
    if cfg.sampling.stop is not None:
        params["stop_sequences"] = cfg.sampling.stop
    if cfg.sampling.reasoning_tokens is not None:
        params["thinking_config"] = {"thinking_budget": cfg.sampling.reasoning_tokens}
    params.update(cfg.runtime.extra)

    client_args: dict[str, Any] = {}
    if cfg.api_key is not None:
        client_args["api_key"] = cfg.api_key
    else:
        vertex_sa_json = os.environ.get("GOOGLE_VERTEX_AI_SERVICE_ACCOUNT")
        if vertex_sa_json:
            try:
                from google.oauth2 import service_account
            except ImportError as e:
                raise ImportError(
                    "Gemini Vertex auth requires google-auth; install the [gemini] extra: "
                    "`pip install 'operad[gemini]'`."
                ) from e

            try:
                sa_info = json.loads(vertex_sa_json)
            except json.JSONDecodeError as e:
                raise BuildError(
                    "bad_config",
                    "GOOGLE_VERTEX_AI_SERVICE_ACCOUNT must be valid JSON.",
                ) from e

            project = os.environ.get("GOOGLE_CLOUD_PROJECT") or sa_info.get("project_id")
            location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            if not project:
                raise BuildError(
                    "bad_config",
                    "Vertex Gemini auth needs project id; set GOOGLE_CLOUD_PROJECT or include project_id in GOOGLE_VERTEX_AI_SERVICE_ACCOUNT.",
                )
            credentials = service_account.Credentials.from_service_account_info(
                sa_info,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            client_args.update(
                {
                    "vertexai": True,
                    "credentials": credentials,
                    "project": project,
                    "location": location,
                }
            )
    if cfg.resilience.timeout is not None:
        # google-genai >= 1.0 uses http_options.timeout (milliseconds); the
        # old top-level `timeout` kwarg was removed.
        client_args["http_options"] = {"timeout": int(cfg.resilience.timeout * 1000)}

    return GeminiModel(
        client_args=client_args or None,
        model_id=cfg.model,
        params=params,
    )


# Pipelines are expensive to construct (multi-second model download + load).
# We intentionally break the "resolve_model returns a fresh object" invariant
# here and cache by (model, device) so repeated resolves for the same config
# share a pipeline. The HF adapter documents this at its public surface.
_HF_PIPELINE_CACHE: dict[tuple[str, str], Any] = {}


def _build_huggingface(cfg: Configuration) -> "Model":
    try:
        import transformers
    except ImportError as e:
        raise ImportError(
            "HuggingFace backend requires the [huggingface] extra: "
            "`pip install 'operad[huggingface]'`."
        ) from e

    if cfg.sampling.seed is not None:
        transformers.set_seed(cfg.sampling.seed)

    device = str(cfg.runtime.extra.get("device", "cpu"))
    key = (cfg.model, device)
    pipe = _HF_PIPELINE_CACHE.get(key)
    if pipe is None:
        pipeline_kwargs: dict[str, Any] = {
            "task": "text-generation",
            "model": cfg.model,
        }
        pipeline_kwargs.update(
            {k: v for k, v in cfg.runtime.extra.items() if k != "device"}
        )
        if device != "cpu":
            pipeline_kwargs["device"] = device
        pipe = transformers.pipeline(**pipeline_kwargs)
        _HF_PIPELINE_CACHE[key] = pipe

    return _HuggingFaceModel(cfg=cfg, pipeline=pipe)


def _build_batch(cfg: Configuration) -> "Model":
    # Validator on Configuration already restricts cfg.backend to openai /
    # anthropic / bedrock when batch=True, so we trust that here.
    return _BatchModel(cfg=cfg)


# --- local / batch model wrappers ------------------------------------------

# These classes satisfy the strands `Model` ABC surface with the minimum
# required to be instantiable. Full stream/structured_output integration
# with the `Agent.invoke` envelope is deferred to a future brief; callers
# use the low-level entry points (`generate` / `forward`) directly.


class _HuggingFaceModel:
    """Thin wrapper around a `transformers.pipeline` for local generation.

    The pipeline is not async; `forward` offloads the call to a worker
    thread. Concurrent invokes against the same pipeline instance will
    serialize — this is a deliberate simplification of Wave 2.
    """

    def __init__(self, cfg: Configuration, pipeline: Any) -> None:
        self._cfg = cfg
        self._pipeline = pipeline
        self.config: dict[str, Any] = {"model_id": cfg.model}

    async def forward(self, prompt: str) -> str:
        import asyncio

        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": self._cfg.sampling.max_tokens,
            "temperature": self._cfg.sampling.temperature,
            "do_sample": self._cfg.sampling.temperature > 0,
        }
        if self._cfg.sampling.top_p is not None:
            gen_kwargs["top_p"] = self._cfg.sampling.top_p
        if self._cfg.sampling.top_k is not None:
            gen_kwargs["top_k"] = self._cfg.sampling.top_k
        if self._cfg.sampling.stop is not None:
            gen_kwargs["stop_strings"] = self._cfg.sampling.stop

        result = await asyncio.to_thread(
            self._pipeline, prompt, **gen_kwargs
        )
        if isinstance(result, list) and result:
            first = result[0]
            if isinstance(first, dict) and "generated_text" in first:
                return str(first["generated_text"])
        return str(result)


class _BatchModel:
    """Submit-only adapter that returns a `BatchHandle` from `forward`.

    Invoking a batch-configured agent through the high-level envelope is
    not supported in Wave 2 — callers must use `forward` directly and
    poll via `poll_batch(handle)`.
    """

    def __init__(self, cfg: Configuration) -> None:
        self._cfg = cfg
        self.config: dict[str, Any] = {
            "model_id": cfg.model,
            "provider": cfg.backend,
        }

    async def forward(self, payload: Any) -> BatchHandle:
        submitter = _BATCH_SUBMITTERS.get(self._cfg.backend)
        if submitter is None:
            raise BuildError(
                "prompt_incomplete",
                f"batch mode is not supported for backend "
                f"{self._cfg.backend!r}",
            )
        raw = await submitter(self._cfg, payload)
        return BatchHandle(
            provider=self._cfg.backend,
            provider_batch_id=str(raw.get("id", "")),
            endpoint=str(raw.get("endpoint", "")),
            submitted_at=time.time(),
            raw=raw,
        )


async def _submit_openai_batch(
    cfg: Configuration, payload: Any
) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=cfg.api_key)
    batch = await client.batches.create(
        input_file_id=payload["input_file_id"],
        endpoint=payload.get("endpoint", "/v1/chat/completions"),
        completion_window=payload.get("completion_window", "24h"),
    )
    raw = batch.model_dump() if hasattr(batch, "model_dump") else dict(batch)
    raw.setdefault("endpoint", payload.get("endpoint", "/v1/chat/completions"))
    return raw


async def _submit_anthropic_batch(
    cfg: Configuration, payload: Any
) -> dict[str, Any]:
    try:
        from anthropic import AsyncAnthropic
    except ImportError as e:  # pragma: no cover - depends on install
        raise ImportError(
            "Anthropic batch requires the `anthropic` package."
        ) from e

    client = AsyncAnthropic(api_key=cfg.api_key)
    batch = await client.messages.batches.create(requests=payload["requests"])
    raw = batch.model_dump() if hasattr(batch, "model_dump") else dict(batch)
    raw.setdefault("endpoint", "/v1/messages/batches")
    return raw


async def _submit_bedrock_batch(
    cfg: Configuration, payload: Any
) -> dict[str, Any]:  # pragma: no cover - network-only
    raise BuildError(
        "prompt_incomplete",
        "bedrock batch submission requires caller-supplied "
        "`CreateModelInvocationJob` parameters; direct boto3 usage is the "
        "Wave 2 path.",
    )


_BATCH_SUBMITTERS = {
    "openai": _submit_openai_batch,
    "anthropic": _submit_anthropic_batch,
    "bedrock": _submit_bedrock_batch,
}


async def poll_batch(handle: BatchHandle) -> BatchResult | None:
    """Return a `BatchResult` when the job is terminal, else `None`."""
    poller = _BATCH_POLLERS.get(handle.provider)
    if poller is None:
        raise BuildError(
            "prompt_incomplete",
            f"batch polling is not supported for backend "
            f"{handle.provider!r}",
        )
    return await poller(handle)


async def _poll_openai_batch(handle: BatchHandle) -> BatchResult | None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    batch = await client.batches.retrieve(handle.provider_batch_id)
    status = getattr(batch, "status", None)
    if status in {"validating", "in_progress", "finalizing"}:
        return None
    if status == "completed":
        return BatchResult(handle=handle, status="completed", output=batch)
    if status == "cancelled":
        return BatchResult(handle=handle, status="cancelled")
    return BatchResult(
        handle=handle, status="failed", error=str(status or "unknown")
    )


async def _poll_anthropic_batch(
    handle: BatchHandle,
) -> BatchResult | None:  # pragma: no cover - network-only
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    batch = await client.messages.batches.retrieve(handle.provider_batch_id)
    status = getattr(batch, "processing_status", None)
    if status == "in_progress":
        return None
    if status == "ended":
        return BatchResult(handle=handle, status="completed", output=batch)
    return BatchResult(
        handle=handle, status="failed", error=str(status or "unknown")
    )


async def _poll_bedrock_batch(
    handle: BatchHandle,
) -> BatchResult | None:  # pragma: no cover - network-only
    raise BuildError(
        "prompt_incomplete",
        "bedrock batch polling is not yet wired; use boto3 directly.",
    )


_BATCH_POLLERS = {
    "openai": _poll_openai_batch,
    "anthropic": _poll_anthropic_batch,
    "bedrock": _poll_bedrock_batch,
}


# --- resolver ---------------------------------------------------------------


_BACKEND_SAMPLING_CAPABILITIES: dict[Backend, frozenset[str]] = {
    "anthropic": frozenset(
        {"temperature", "max_tokens", "top_p", "top_k", "stop", "reasoning_tokens"}
    ),
    "bedrock": frozenset(
        {"temperature", "max_tokens", "top_p", "top_k", "seed", "stop"}
    ),
    "llamacpp": frozenset(
        {"temperature", "max_tokens", "top_p", "top_k", "seed", "stop", "reasoning_tokens"}
    ),
    "lmstudio": frozenset(
        {"temperature", "max_tokens", "top_p", "top_k", "seed", "stop", "reasoning_tokens"}
    ),
    "ollama": frozenset({"temperature", "max_tokens", "top_p", "stop"}),
    "openai": frozenset(
        {"temperature", "max_tokens", "top_p", "top_k", "seed", "stop", "reasoning_tokens"}
    ),
    "gemini": frozenset(
        {"temperature", "max_tokens", "top_p", "top_k", "seed", "stop", "reasoning_tokens"}
    ),
    "huggingface": frozenset(
        {"temperature", "max_tokens", "top_p", "top_k", "seed", "stop"}
    ),
}


def _warn_dead_sampling_knobs(cfg: Configuration) -> None:
    honoured = _BACKEND_SAMPLING_CAPABILITIES.get(cfg.backend, frozenset())
    user_set = cfg.sampling.model_fields_set
    for field in sorted(user_set - honoured):
        warnings.warn(
            f"Configuration.sampling.{field} is set but backend "
            f"{cfg.backend!r} does not consume it; the value will be ignored.",
            UserWarning,
            stacklevel=3,
        )


def resolve_model(cfg: Configuration) -> "Model":
    """Return a configured `strands.models.Model` for the given configuration."""
    _warn_dead_sampling_knobs(cfg)
    if cfg.batch:
        return _build_batch(cfg)
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
        case "gemini":
            return _build_gemini(cfg)
        case "huggingface":
            return _build_huggingface(cfg)
        case other:
            raise BuildError(
                "prompt_incomplete",
                f"unknown backend {other!r}",
            )


__all__ = ["BatchHandle", "BatchResult", "poll_batch", "resolve_model"]
