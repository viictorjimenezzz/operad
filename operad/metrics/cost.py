"""Rough cost / token aggregator.

Subscribes to per-invoke events — either the eventual Stream-C
`AgentEvent`, or the local stub `_CostEvent` below — and accumulates
estimated token counts and USD by run.

First-cut heuristics:
- tokens ≈ `len(text) // 4`  (character/4, no real tokenizer)
- prices are a tiny hard-coded table keyed by `(backend, model)`

Real tokenisation and real pricing come later. Do not build a parallel
event bus — when Stream C lands, swap `_CostEvent` for
`operad.core.observer.AgentEvent` in one place.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


# Dollars per 1k tokens; prompt / completion separately. Rough starter
# set; keep tiny. Unknown (backend, model) → (0.0, 0.0).
_PRICE_TABLE: dict[tuple[str, str], tuple[float, float]] = {
    ("llamacpp", "default"): (0.0, 0.0),
    ("anthropic", "claude-haiku-4-5"): (0.001, 0.005),
    ("anthropic", "claude-sonnet-4-6"): (0.003, 0.015),
    ("anthropic", "claude-opus-4-7"): (0.015, 0.075),
    ("openai", "gpt-4o-mini"): (0.00015, 0.0006),
    ("openai", "gpt-4o"): (0.0025, 0.01),
}


def _estimate_tokens(text: str) -> int:
    return max(0, len(text) // 4)


def _price(backend: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_rate, completion_rate = _PRICE_TABLE.get((backend, model), (0.0, 0.0))
    return (prompt_tokens * prompt_rate + completion_tokens * completion_rate) / 1000.0


@dataclass
class _CostEvent:
    """Stub event shape consumed by `CostTracker`.

    Mirrors the minimum surface the Stream-C `AgentEvent` will expose.
    When Stream C lands, delete this class and import `AgentEvent`
    instead; `CostTracker.on_event` reads only these attributes.
    """

    run_id: str
    backend: str
    model: str
    prompt_text: str = ""
    completion_text: str = ""


@dataclass
class CostTracker:
    """Accumulates token and cost totals keyed by `run_id`.

    Not itself a `Metric` — exposes `totals()` for reporting. Attach
    `on_event` to the observer registry once Stream C is in place.
    """

    _totals: dict[str, dict[str, float]] = field(
        default_factory=lambda: defaultdict(
            lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
        )
    )

    async def on_event(self, event: Any) -> None:
        prompt_tokens = _estimate_tokens(getattr(event, "prompt_text", "") or "")
        completion_tokens = _estimate_tokens(
            getattr(event, "completion_text", "") or ""
        )
        cost = _price(event.backend, event.model, prompt_tokens, completion_tokens)
        bucket = self._totals[event.run_id]
        bucket["prompt_tokens"] += prompt_tokens
        bucket["completion_tokens"] += completion_tokens
        bucket["cost_usd"] += cost

    def totals(self) -> dict[str, dict[str, float]]:
        return {run_id: dict(v) for run_id, v in self._totals.items()}
