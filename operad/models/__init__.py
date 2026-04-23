"""Backend resolver: maps a `Configuration` to a concrete `strands.models.Model`.

Every local-first backend keeps a one-file adapter under this package. The
public entry point is `resolve_model(cfg)`, which dispatches on
`cfg.backend`. Each adapter is responsible for threading *all* relevant
`Configuration` fields into that backend's native constructor (no silent
drops of temperature, seed, stop, etc.).
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
