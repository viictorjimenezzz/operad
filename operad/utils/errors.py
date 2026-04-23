"""Error types for the operad library.

A single exception is used with a `reason` literal so callers can branch on
the kind of failure without matching multiple classes.
"""

from __future__ import annotations

from typing import Literal

BuildReason = Literal[
    "not_built",
    "prompt_incomplete",
    "input_mismatch",
    "output_mismatch",
    "trace_failed",
    "payload_branch",
    "router_miss",
]


class BuildError(Exception):
    """Raised by build-time checks and by framework-level contract guards.

    Attributes:
        reason: A short literal identifying the failure category.
        agent:  Optional qualified name of the agent involved.
    """

    reason: BuildReason
    agent: str | None

    def __init__(
        self,
        reason: BuildReason,
        message: str,
        *,
        agent: str | None = None,
    ) -> None:
        self.reason = reason
        self.agent = agent
        prefix = f"[{reason}]"
        if agent:
            prefix = f"{prefix} {agent}:"
        super().__init__(f"{prefix} {message}")
