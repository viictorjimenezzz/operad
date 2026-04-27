from __future__ import annotations

"""Structured exceptions for the uthereal bridge.

Owner: 1-1-skeleton.
"""

from typing import Any


class UtherealBridgeError(Exception):
    """Base class for user-facing uthereal bridge errors."""

    def __init__(self, *, reason: str, **details: Any) -> None:
        self.reason = reason
        self.details = details
        detail_text = ", ".join(f"{key}={value!r}" for key, value in details.items())
        message = reason if not detail_text else f"{reason}: {detail_text}"
        super().__init__(message)


class LoaderError(UtherealBridgeError):
    """Raised when YAML or tier configuration cannot be loaded."""


class RetrievalError(UtherealBridgeError):
    """Raised when retrieval cannot complete under the configured policy."""


class TraceError(UtherealBridgeError):
    """Raised when a workflow trace is missing, malformed, or inconsistent."""
