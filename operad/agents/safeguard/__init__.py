"""Task-agnostic safeguard domain: generic input/output guardrail leaves.

This domain complements the conversation-flavoured
:class:`operad.agents.conversational.Safeguard` with two generic leaves
that drop into any pipeline:

- :class:`InputSanitizer` — override-forward, deterministic redaction
  and truncation of string fields on an arbitrary Pydantic payload.
- :class:`OutputModerator` — default-forward, LLM-backed classifier
  that emits a :class:`ModerationVerdict` (``allow`` / ``block``).

Typical composition via :class:`operad.agents.Pipeline`::

    pipe = Pipeline(
        InputSanitizer(schema=Question),
        Reasoner(config=cfg, input=Question, output=Answer),
        OutputModerator(schema=Answer, config=cfg),
        input=Question,
        output=ModerationVerdict,
    )

Or by wrapping a leaf with custom forward hooks once those land (see
brief 2-1)::

    class SafeReasoner(Reasoner):
        def forward_in(self, x): return _san.forward_sync(x)
        def forward_out(self, x, y): ...  # gate on verdict

Both leaves are generic — construct with the concrete payload type
you're guarding. Dispatching on ``verdict.label`` is the caller's
responsibility (use a :class:`Switch`); nothing in this domain routes
on payload values.
"""

from __future__ import annotations

from .components import InputSanitizer, OutputModerator
from .schemas import ModerationVerdict, SanitizerPolicy

__all__ = [
    "InputSanitizer",
    "ModerationVerdict",
    "OutputModerator",
    "SanitizerPolicy",
]
