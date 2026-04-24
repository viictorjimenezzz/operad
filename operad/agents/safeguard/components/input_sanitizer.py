"""Override-forward leaf that sanitises string fields on an arbitrary payload."""

from __future__ import annotations

import re
from typing import Generic, TypeVar

from pydantic import BaseModel

from ....core.agent import Agent
from ..schemas import SanitizerPolicy

T = TypeVar("T", bound=BaseModel)


_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\bSSN-\d+\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
)


class InputSanitizer(Agent[T, T], Generic[T]):
    """Pass-through leaf that redacts/truncates string fields in ``T``.

    Walks the payload's Pydantic fields, applies the configured
    ``SanitizerPolicy`` to any ``str``-valued field, and returns a new
    instance of ``T`` with sanitised values. Non-string fields pass
    through untouched. Override :meth:`sanitize_str` to plug in custom
    redaction (Presidio, a profanity filter, …) without rewriting the
    field walk.

    This leaf never contacts a model: it is constructed with
    ``config=None`` and runs deterministically inside ``forward``.
    """

    input = BaseModel
    output = BaseModel

    role = "Sanitise string fields in the incoming payload before downstream use."
    task = (
        "Apply the configured SanitizerPolicy to every string field: "
        "redact matches of the policy pattern, truncate to max_chars, "
        "strip PII-like substrings when enabled."
    )
    rules = (
        "Do not alter non-string fields.",
        "Preserve the original field names exactly.",
        "Return a new instance; do not mutate the input in place.",
    )

    def __init__(
        self,
        *,
        schema: type[T],
        policy: SanitizerPolicy | None = None,
    ) -> None:
        super().__init__(config=None, input=schema, output=schema)
        self._policy = policy or SanitizerPolicy()

    def sanitize_str(self, s: str) -> str:
        out = s
        if self._policy.strip_pii:
            for pat in _PII_PATTERNS:
                out = pat.sub("[REDACTED]", out)
        if self._policy.redact_pattern:
            out = re.sub(self._policy.redact_pattern, "[REDACTED]", out)
        if self._policy.max_chars is not None:
            out = out[: self._policy.max_chars]
        if self._policy.lowercase:
            out = out.lower()
        return out

    async def forward(self, x: T) -> T:  # type: ignore[override]
        cls = type(x)
        updates: dict[str, str] = {}
        for name in cls.model_fields:
            value = getattr(x, name)
            if isinstance(value, str):
                updates[name] = self.sanitize_str(value)
        if not updates:
            return x.model_copy()
        return x.model_copy(update=updates)
