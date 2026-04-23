"""Runtime primitives: concurrency slots today, observers later."""

from __future__ import annotations

from .slots import SlotRegistry, acquire, registry, set_limit

__all__ = ["SlotRegistry", "acquire", "registry", "set_limit"]
