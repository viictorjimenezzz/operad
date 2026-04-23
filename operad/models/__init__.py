"""Backend resolver: maps a `Configuration` to a concrete `strands.models.Model`.

Every local-first backend keeps a one-file adapter under this package. The
public entry point is `resolve_model(cfg)`, which dispatches on
`cfg.backend`. Each adapter is responsible for threading *all* relevant
`Configuration` fields into that backend's native constructor (no silent
drops of temperature, seed, stop, etc.).

Per-backend handling of `Configuration` knobs:

| Backend   | `extra` destination                      | reasoning_tokens        | timeout | max_retries |
| --------- | ---------------------------------------- | ----------------------- | ------- | ----------- |
| llamacpp  | splatted into `params` dict              | max_completion_tokens   | —       | —           |
| lmstudio  | splatted into `params` dict              | max_completion_tokens   | ✓       | ✓           |
| ollama    | wrapped as `options` dict                | —                       | —       | —           |
| openai    | splatted into `params` dict              | max_completion_tokens   | ✓       | ✓           |
| bedrock   | splatted as top-level BedrockModel kwargs | —                      | —       | —           |

- `extra` semantics match what each backend's native SDK accepts.
- `top_k` and `seed` on bedrock are threaded via `additional_request_fields`;
  other backends put them in their params / kwargs directly.
- `backoff_base` is not consumed by any adapter; it is reserved for
  observer-driven retry logic in `operad.runtime`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.config import Configuration
from ..utils.errors import BuildError
from .bedrock import build as _build_bedrock
from .llamacpp import build as _build_llamacpp
from .lmstudio import build as _build_lmstudio
from .ollama import build as _build_ollama
from .openai import build as _build_openai

if TYPE_CHECKING:
    from strands.models.model import Model


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
        case other:
            raise BuildError(
                "prompt_incomplete",
                f"unknown backend {other!r}",
            )


__all__ = ["resolve_model"]
