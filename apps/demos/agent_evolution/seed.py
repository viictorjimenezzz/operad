"""Offline seed agent for the agent_evolution showcase.

The leaf's output is a deterministic function of prompt/config state.
That lets `EvoGradient` drive fitness upward by accumulating useful
mutations without ever contacting a model server.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.core.config import Sampling


class Q(BaseModel):
    text: str = Field(default="", description="The question being asked.")


class R(BaseModel):
    value: int = Field(default=0, description="Answer derived from the leaf's mutation state.")


class RuleCountLeaf(Agent[Q, R]):
    """A synthetic leaf whose output rewards accumulated useful mutations."""

    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        score = len(self.rules)
        if "precise" in (self.role or "").lower():
            score += 1
        if "rank" in (self.task or "").lower():
            score += 1
        if self.config is not None and 0.2 <= self.config.sampling.temperature <= 0.5:
            score += 1
        return R.model_construct(value=score)


def build_seed() -> RuleCountLeaf:
    """Construct the unbuilt seed used by `run.py`.

    The config is a placeholder: the leaf overrides `forward` so
    no backend is ever contacted.
    """
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="demo",
        sampling=Sampling(temperature=0.0, max_tokens=16),
    )
    seed = RuleCountLeaf(config=cfg)
    seed.role = "You are a concise evaluator."
    seed.task = "Score the answer."
    seed.rules = ["Answer directly.", "Use evidence when available."]
    seed.mark_trainable(role=True, task=True, rules=True, temperature=True)
    return seed
