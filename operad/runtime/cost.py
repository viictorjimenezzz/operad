"""Cost / token estimation — live tracker and post-hoc trace estimator.

Two consumer shapes share one pricing table and helpers:

- ``cost_estimate(trace, ...)``: a free function that walks a completed
  ``Trace`` and returns a ``CostReport``. Uses each step's
  ``OperadOutput.prompt_tokens`` / ``completion_tokens`` when the
  provider populated them; otherwise falls back to a rough
  ``len(text) // 4`` heuristic.
- ``CostTracker``: an observer-style accumulator keyed by ``run_id``.
  Its ``on_event`` method accepts the transitional ``_CostEvent`` stub
  below. Once the Wave-4 algorithm events land, the tracker will read
  tokens and ``backend``/``model`` directly off the real
  ``AgentEvent`` — the surface here stays stable.

``CostTracker`` is also re-exported from ``operad.metrics`` so existing
callers (and the docs) keep working.
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from .trace import Trace


# Dollars per 1k tokens; (prompt_rate, completion_rate) per "backend:model".
# Keep tiny and boring; callers can supply `pricing=` to extend.
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "llamacpp:default": (0.0, 0.0),
    "anthropic:claude-haiku-4-5": (0.001, 0.005),
    "anthropic:claude-sonnet-4-6": (0.003, 0.015),
    "anthropic:claude-opus-4-7": (0.015, 0.075),
    "openai:gpt-4o-mini": (0.00015, 0.0006),
    "openai:gpt-4o": (0.0025, 0.01),
}


@dataclass(frozen=True)
class Pricing:
    """Per-1k-token rates for one `backend:model` pair."""

    prompt_per_1k: float
    completion_per_1k: float


class CostReport(BaseModel):
    """Trace-level totals + per-step breakdown."""

    run_id: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    per_step: list[dict[str, float | int | str]] = []


def _default_tokenizer(text: str) -> int:
    return max(0, len(text) // 4)


def cost_estimate(
    trace: Trace,
    *,
    pricing: dict[str, Pricing] | None = None,
    tokenizer: Callable[[str], int] = _default_tokenizer,
) -> CostReport:
    """Estimate total tokens and USD spend for a completed `Trace`.

    `pricing` keys are `"<backend>:<model>"`; missing keys → free.
    When a step lacks `prompt_tokens`/`completion_tokens`, falls back
    to `tokenizer` over the step's stored prompt (no completion text
    is retained in the trace, so completion tokens default to 0 in the
    fallback path).
    """
    prompt_total = 0
    completion_total = 0
    cost_total = 0.0
    per_step: list[dict[str, float | int | str]] = []

    for step in trace.steps:
        out = step.output
        p_toks = out.prompt_tokens
        c_toks = out.completion_tokens
        if p_toks is None:
            p_toks = tokenizer("")
        if c_toks is None:
            c_toks = 0

        key = _pricing_key_for_step(out)
        rate = _lookup_rate(pricing, key)
        cost = (p_toks * rate.prompt_per_1k + c_toks * rate.completion_per_1k) / 1000.0

        prompt_total += p_toks
        completion_total += c_toks
        cost_total += cost

        per_step.append(
            {
                "agent_path": step.agent_path,
                "prompt_tokens": int(p_toks),
                "completion_tokens": int(c_toks),
                "cost_usd": float(cost),
            }
        )

    return CostReport(
        run_id=trace.run_id,
        prompt_tokens=prompt_total,
        completion_tokens=completion_total,
        cost_usd=cost_total,
        per_step=per_step,
    )


def _pricing_key_for_step(out: Any) -> str:
    """Build the ``"backend:model"`` key for one step's envelope.

    Reads ``backend`` / ``model`` directly off ``OperadOutput``. Empty
    values fall back to ``"unknown:unknown"`` — those rows price to
    zero under the default table.
    """
    backend = getattr(out, "backend", "") or "unknown"
    model = getattr(out, "model", "") or "unknown"
    return f"{backend}:{model}"


def _lookup_rate(
    pricing: dict[str, Pricing] | None, key: str
) -> Pricing:
    if pricing is not None and key in pricing:
        return pricing[key]
    if key in PRICE_TABLE:
        p, c = PRICE_TABLE[key]
        return Pricing(prompt_per_1k=p, completion_per_1k=c)
    return Pricing(prompt_per_1k=0.0, completion_per_1k=0.0)


@dataclass
class _CostEvent:
    """Transitional event shape consumed by ``CostTracker``.

    Carries the minimum surface CostTracker needs — ``run_id``,
    ``backend``, ``model``, and raw text for char-based tokenization.
    The live algorithm-event schema landing later in Wave 4 will
    supersede this stub; ``CostTracker.on_event`` reads only these
    attributes so the swap is one-sided.
    """

    run_id: str
    backend: str
    model: str
    prompt_text: str = ""
    completion_text: str = ""

    def __post_init__(self) -> None:
        warnings.warn(
            "_CostEvent is deprecated; use CostObserver with the live "
            "AgentEvent stream. _CostEvent will be removed in Wave 5.",
            DeprecationWarning,
            stacklevel=2,
        )


def _price(backend: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate = _lookup_rate(None, f"{backend}:{model}")
    return (
        prompt_tokens * rate.prompt_per_1k + completion_tokens * rate.completion_per_1k
    ) / 1000.0


@dataclass
class CostTracker:
    """Accumulates token and cost totals keyed by ``run_id``.

    Not itself a ``Metric`` — exposes ``totals()`` for reporting.
    Register ``on_event`` on the observer registry to accumulate in
    real time.
    """

    _totals: dict[str, dict[str, float]] = field(
        default_factory=lambda: defaultdict(
            lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
        )
    )

    async def on_event(self, event: Any) -> None:
        prompt_tokens = _default_tokenizer(getattr(event, "prompt_text", "") or "")
        completion_tokens = _default_tokenizer(
            getattr(event, "completion_text", "") or ""
        )
        cost = _price(event.backend, event.model, prompt_tokens, completion_tokens)
        bucket = self._totals[event.run_id]
        bucket["prompt_tokens"] += prompt_tokens
        bucket["completion_tokens"] += completion_tokens
        bucket["cost_usd"] += cost

    def totals(self) -> dict[str, dict[str, float]]:
        return {run_id: dict(v) for run_id, v in self._totals.items()}


@dataclass
class CostObserver:
    """Observer that accumulates token + USD spend per ``run_id``.

    Reads ``backend``, ``model``, ``prompt_tokens``, ``completion_tokens``
    directly off ``AgentEvent.output`` on ``kind == "end"`` events; other
    event kinds (and those lacking an envelope, e.g. algorithm events)
    are ignored. Delegates storage to an internal ``CostTracker``; expose
    ``totals()`` for read-through. Register with
    ``operad.runtime.observers.registry.register(obs)``.
    """

    tracker: CostTracker = field(default_factory=CostTracker)
    pricing: dict[str, Pricing] | None = None

    async def on_event(self, event: Any) -> None:
        if getattr(event, "kind", None) != "end":
            return
        out = getattr(event, "output", None)
        if out is None:
            return
        p = getattr(out, "prompt_tokens", None) or 0
        c = getattr(out, "completion_tokens", None) or 0
        backend = getattr(out, "backend", "") or "unknown"
        model = getattr(out, "model", "") or "unknown"
        rate = _lookup_rate(self.pricing, f"{backend}:{model}")
        cost = (p * rate.prompt_per_1k + c * rate.completion_per_1k) / 1000.0
        run_id = getattr(out, "run_id", "") or getattr(event, "run_id", "")
        bucket = self.tracker._totals[run_id]
        bucket["prompt_tokens"] += p
        bucket["completion_tokens"] += c
        bucket["cost_usd"] += cost

    def totals(self) -> dict[str, dict[str, float]]:
        return self.tracker.totals()


__all__ = [
    "CostObserver",
    "CostReport",
    "CostTracker",
    "PRICE_TABLE",
    "Pricing",
    "_CostEvent",
    "cost_estimate",
]
