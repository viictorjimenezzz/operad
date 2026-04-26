"""Backward-compatible task-agnostic safeguard primitives.

These are lightweight local components kept for test and API compatibility.
"""

from __future__ import annotations

import re
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field

from ...core.agent import Agent


T = TypeVar("T", bound=BaseModel)


class SanitizerPolicy(BaseModel):
    """String-field sanitization policy."""

    strip_pii: bool = Field(
        default=True,
        description="When true, redact common PII patterns before custom rules.",
    )
    redact_pattern: str | None = Field(
        default=None,
        description="Optional regex pattern to redact with [REDACTED].",
    )
    max_chars: int | None = Field(
        default=None,
        description="Optional max length for string fields after redaction.",
    )


class ModerationVerdict(BaseModel):
    """Simple moderation outcome."""

    label: Literal["allow", "block"] = "allow"
    reason: str = ""


class InputSanitizer(Agent[T, T]):
    """Deterministic sanitizer over typed payloads."""

    def __init__(
        self,
        *,
        schema: type[T],
        policy: SanitizerPolicy | None = None,
    ) -> None:
        super().__init__(input=schema, output=schema)
        self.policy = policy or SanitizerPolicy()

    async def forward(self, x: T) -> T:  # type: ignore[override]
        payload = x.model_dump(mode="python")
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str):
                out[key] = self._sanitize_text(value)
            else:
                out[key] = value
        return self.output.model_validate(out)  # type: ignore[return-value]

    def _sanitize_text(self, text: str) -> str:
        p = self.policy
        result = text
        if p.strip_pii:
            # Keep this intentionally conservative and local.
            result = re.sub(r"\b[\w.+-]+@[\w.-]+\.\w+\b", "[REDACTED]", result)
            result = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED]", result)
        if p.redact_pattern:
            result = re.sub(p.redact_pattern, "[REDACTED]", result)
        if p.max_chars is not None and p.max_chars >= 0:
            result = result[: p.max_chars]
        return result


class OutputModerator(Agent[T, ModerationVerdict]):
    """Typed moderation leaf with a conservative default policy."""

    output = ModerationVerdict

    def __init__(self, *, schema: type[T], config: Any | None = None) -> None:
        super().__init__(input=schema, output=ModerationVerdict, config=config)

    async def forward(self, x: T) -> ModerationVerdict:  # type: ignore[override]
        _ = x
        return ModerationVerdict(label="allow", reason="passed")


__all__ = [
    "InputSanitizer",
    "ModerationVerdict",
    "OutputModerator",
    "SanitizerPolicy",
]

