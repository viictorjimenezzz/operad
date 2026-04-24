"""Schemas for the task-agnostic safeguard domain."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModerationVerdict(BaseModel):
    """A binary allow/block verdict with a short rationale."""

    label: Literal["allow", "block"] = Field(
        default="allow",
        description="Whether the payload is safe to release downstream.",
    )
    reason: str = Field(
        default="",
        description="Short rationale for the verdict (at most two sentences).",
    )
    categories: list[str] = Field(
        default_factory=list,
        description=(
            "Optional policy categories triggered by the payload "
            "(e.g. 'pii', 'toxicity')."
        ),
    )


class SanitizerPolicy(BaseModel):
    """Declarative sanitisation rules consumed by `InputSanitizer`."""

    strip_pii: bool = Field(
        default=True,
        description=(
            "When True, apply a minimal set of PII regexes "
            "(SSN-style, email, phone) before any custom redaction."
        ),
    )
    max_chars: int | None = Field(
        default=None,
        description="Truncate string fields to this many characters when set.",
    )
    redact_pattern: str | None = Field(
        default=None,
        description=(
            "Regex; every match in every string field is replaced "
            "with '[REDACTED]'."
        ),
    )
    lowercase: bool = Field(
        default=False,
        description="Lowercase every string field after redaction/truncation.",
    )
