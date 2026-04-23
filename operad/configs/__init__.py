"""YAML config loading for the `operad` CLI."""

from __future__ import annotations

from .loader import ConfigError, apply_runtime, instantiate, load
from .schema import OverrideSpec, RunConfig, RuntimeSpec, SlotSpec

__all__ = [
    "ConfigError",
    "OverrideSpec",
    "RunConfig",
    "RuntimeSpec",
    "SlotSpec",
    "apply_runtime",
    "instantiate",
    "load",
]
