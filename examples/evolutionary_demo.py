"""`EvoGradient` evolving a seed against a 5-row dataset.

Runs offline — no model server required. The seed leaf's output depends
deterministically on its rule count, so applying `AppendRule` across
generations nudges the population toward a target score. The demo
prints the seed's score, the best score per generation, and the final
evolved agent's change (rule count, rules).

Run:
    uv run python examples/evolutionary_demo.py [--offline]
"""

from __future__ import annotations

import argparse
import asyncio
import random

from pydantic import BaseModel

from operad import Agent, Configuration, evaluate
from operad.core.config import Sampling
from operad.metrics.base import MetricBase
from operad.optim import EvoGradient
from operad.utils.ops import AppendRule


class Q(BaseModel):
    text: str = ""


class R(BaseModel):
    value: int = 0


class RuleCountLeaf(Agent[Q, R]):
    """A toy offline leaf whose output equals its number of rules."""

    input = Q
    output = R

    async def forward(self, x: Q) -> R:  # type: ignore[override]
        return R.model_construct(value=len(self.rules))


class RuleCountMetric(MetricBase):
    """Scores predicted.value toward a target rule count (offline)."""

    name = "rule_count"

    def __init__(self, target: int) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


async def main(offline: bool = False) -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="demo",
        sampling=Sampling(temperature=0.0, max_tokens=16),
    )

    seed = RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    dataset = [(Q(text=str(i)), R(value=3)) for i in range(5)]
    metric = RuleCountMetric(target=3)

    seed_report = await evaluate(seed, dataset, [metric])
    print(f"seed rule_count={len(seed.rules)}, score={seed_report.summary[metric.name]:.3f}")

    generations = 4
    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=[AppendRule(path="", rule="be helpful")],
        metric=metric,
        dataset=dataset,
        population_size=6,
        rng=random.Random(0),
    )
    for _ in range(generations):
        await optimizer.step()

    best_report = await evaluate(seed, dataset, [metric])
    print(f"best rule_count={len(seed.rules)}, score={best_report.summary[metric.name]:.3f}")
    print("best.rules:")
    for i, r in enumerate(seed.rules):
        print(f"  {i}: {r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run without contacting any LLM server.",
    )
    args = parser.parse_args()
    asyncio.run(main(offline=args.offline))
