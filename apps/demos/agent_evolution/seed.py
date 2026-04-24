"""Offline seed agent for the agent_evolution showcase.

The leaf's output is a deterministic function of its `rules` length.
That lets `Evolutionary` drive fitness upward by appending rules,
without ever contacting a model server.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.core.config import Sampling


class Q(BaseModel):
    text: str = Field(default="", description="The question being asked.")


class R(BaseModel):
    value: int = Field(default=0, description="Answer derived from the leaf's rule count.")


class RuleCountLeaf(Agent[Q, R]):
    """A synthetic leaf whose output equals `len(self.rules)`."""

    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        return R.model_construct(value=len(self.rules))


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
    seed.rules = []
    return seed
