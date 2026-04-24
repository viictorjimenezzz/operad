"""YAML → `RunConfig` → instantiated `Agent`."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..core.agent import Agent
from ..runtime.slots import set_limit
from .schema import RunConfig


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


def _import_by_path(dotted: str) -> type[Agent[Any, Any]]:
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


def instantiate(rc: RunConfig) -> Agent[Any, Any]:
    """Import the configured Agent class and construct an instance.

    Does not call `build()` — callers decide when to build (CLI `run`,
    `trace`, `graph` each trigger it at the appropriate point).
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
    for s in rc.runtime.slots:
        set_limit(backend=s.backend, host=s.host, concurrency=s.limit)
