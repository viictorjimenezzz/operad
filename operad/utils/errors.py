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
    "schema_drift",
    "sentinel_bypass",
]


class BuildError(Exception):
    """Raised by build-time checks and by framework-level contract guards.

    Attributes:
        reason:  A short literal identifying the failure category.
        agent:   Optional qualified name of the agent involved.
        mermaid: Optional Mermaid ``flowchart`` fragment highlighting the
                 failing edge or node. Appended to ``str(exc)`` after a
                 ``--- mermaid ---`` marker. The first line (``[reason]
                 agent: message``) is unchanged so existing log regexes
                 keep working.
    """

    reason: BuildReason
    agent: str | None
    mermaid: str | None

    def __init__(
        self,
        reason: BuildReason,
        message: str,
        *,
        agent: str | None = None,
        mermaid: str | None = None,
    ) -> None:
        self.reason = reason
        self.agent = agent
        self.mermaid = mermaid
        prefix = f"[{reason}]"
        if agent:
            prefix = f"{prefix} {agent}:"
        super().__init__(f"{prefix} {message}")

    def __str__(self) -> str:
        base = super().__str__()
        if self.mermaid:
            return f"{base}\n\n--- mermaid ---\n{self.mermaid}"
        return base


class SideEffectDuringTrace(UserWarning):
    """Emitted when a composite traces branches that may have side effects.

    Users can silence globally with
    ``warnings.filterwarnings("ignore", category=SideEffectDuringTrace)``.
    """
