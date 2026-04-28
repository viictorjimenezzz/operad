from __future__ import annotations

"""Structured exceptions for the uthereal bridge.

Owner: 1-1-skeleton.
"""

from pathlib import Path
from typing import Any


class UtherealBridgeError(Exception):
    """Base class for user-facing uthereal bridge errors.

    Accepts either of these call shapes (both used across the codebase):

    - ``LoaderError(yaml_path, "reason", **details)`` -- the loader pattern,
      where the first positional argument is the offending YAML path and the
      second positional is the structured reason code.
    - ``LoaderError(reason="reason", **details)`` -- the tier/runner pattern,
      where there is no associated path.
    """

    def __init__(
        self,
        yaml_path: Path | str | None = None,
        reason: str | None = None,
        **details: Any,
    ) -> None:
        self.yaml_path = Path(yaml_path) if yaml_path is not None else None
        self.reason = reason or ""
        self.details = details
        for key, value in details.items():
            setattr(self, key, value)
        detail_text = ", ".join(f"{key}={value!r}" for key, value in details.items())
        if self.yaml_path is not None:
            prefix = f"[{self.reason}] {self.yaml_path}" if self.reason else str(self.yaml_path)
        else:
            prefix = self.reason
        message = prefix if not detail_text else f"{prefix}: {detail_text}"
        super().__init__(message)


class LoaderError(UtherealBridgeError):
    """Raised when YAML or tier configuration cannot be loaded."""


class RetrievalError(UtherealBridgeError):
    """Raised when retrieval cannot complete under the configured policy."""


class TraceError(UtherealBridgeError):
    """Raised when a workflow trace is missing, malformed, or inconsistent."""
