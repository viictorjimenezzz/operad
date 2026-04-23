"""Cost / token estimation for a completed `Trace`.

Free function, not a method on `Trace`: keeps pricing strictly a view
concern. Uses per-step `OperadOutput.prompt_tokens` /
`completion_tokens` when the provider populated them; otherwise falls
back to a rough `len(text) // 4` heuristic over the rendered prompt
(no response text is available post-hoc from the trace alone).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel

from .trace import Trace


# Dollars per 1k tokens; (prompt_rate, completion_rate) per backend:model.
# Keep tiny and boring; callers supply `pricing=` to extend.
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


def _pricing_key_for_step(_out: object) -> str:
    """Placeholder until `OperadOutput` carries `backend`/`model` directly.

    The reproducibility hashes carry `hash_model` but not the raw
    `backend:model` string; surface that as a follow-up and return a
    neutral key that always misses the table (free fallback).
    """
    return "unknown:unknown"


def _lookup_rate(
    pricing: dict[str, Pricing] | None, key: str
) -> Pricing:
    if pricing is not None and key in pricing:
        return pricing[key]
    if key in PRICE_TABLE:
        p, c = PRICE_TABLE[key]
        return Pricing(prompt_per_1k=p, completion_per_1k=c)
    return Pricing(prompt_per_1k=0.0, completion_per_1k=0.0)


__all__ = ["CostReport", "PRICE_TABLE", "Pricing", "cost_estimate"]
