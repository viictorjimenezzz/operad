"""Cost / token estimation metrics and observers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from ..runtime.trace import Trace


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
    """Estimate total tokens and USD spend for a completed `Trace`."""
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
    backend = getattr(out, "backend", "") or "unknown"
    model = getattr(out, "model", "") or "unknown"
    return f"{backend}:{model}"


def _lookup_rate(pricing: dict[str, Pricing] | None, key: str) -> Pricing:
    if pricing is not None and key in pricing:
        return pricing[key]
    if key in PRICE_TABLE:
        p, c = PRICE_TABLE[key]
        return Pricing(prompt_per_1k=p, completion_per_1k=c)
    return Pricing(prompt_per_1k=0.0, completion_per_1k=0.0)


def _price(
    backend: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing: dict[str, Pricing] | None = None,
) -> float:
    rate = _lookup_rate(pricing, f"{backend}:{model}")
    return (
        prompt_tokens * rate.prompt_per_1k + completion_tokens * rate.completion_per_1k
    ) / 1000.0


@dataclass
class CostTracker:
    """Accumulates token and cost totals keyed by ``run_id``."""

    pricing: dict[str, Pricing] | None = None
    _totals: dict[str, dict[str, float]] = field(
        default_factory=lambda: defaultdict(
            lambda: {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
        )
    )

    def add(
        self,
        *,
        run_id: str,
        backend: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        cost = _price(
            backend,
            model,
            prompt_tokens,
            completion_tokens,
            pricing=self.pricing,
        )
        bucket = self._totals[run_id]
        bucket["prompt_tokens"] += prompt_tokens
        bucket["completion_tokens"] += completion_tokens
        bucket["cost_usd"] += cost

    async def on_event(self, event: Any) -> None:
        if getattr(event, "kind", None) != "end":
            return
        out = getattr(event, "output", None)
        if out is None:
            return
        self.add(
            run_id=getattr(out, "run_id", "") or getattr(event, "run_id", ""),
            backend=getattr(out, "backend", "") or "unknown",
            model=getattr(out, "model", "") or "unknown",
            prompt_tokens=int(getattr(out, "prompt_tokens", None) or 0),
            completion_tokens=int(getattr(out, "completion_tokens", None) or 0),
        )

    def totals(self) -> dict[str, dict[str, float]]:
        return {run_id: dict(v) for run_id, v in self._totals.items()}


@dataclass
class CostObserver:
    """Observer that accumulates token + USD spend per ``run_id``."""

    tracker: CostTracker = field(default_factory=CostTracker)
    pricing: dict[str, Pricing] | None = None

    async def on_event(self, event: Any) -> None:
        if self.tracker.pricing is None:
            self.tracker.pricing = self.pricing
        await self.tracker.on_event(event)

    def totals(self) -> dict[str, dict[str, float]]:
        return self.tracker.totals()


__all__ = [
    "CostObserver",
    "CostReport",
    "CostTracker",
    "PRICE_TABLE",
    "Pricing",
    "cost_estimate",
]
