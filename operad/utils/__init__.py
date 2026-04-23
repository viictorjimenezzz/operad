"""Small cross-cutting helpers shared by the foundation and plugins."""

from __future__ import annotations

from .errors import BuildError, BuildReason

__all__ = ["BuildError", "BuildReason"]
