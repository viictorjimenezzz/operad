"""`Evolutionary` evolving a seed against a 5-row dataset.

Runs offline — no model server required. The seed leaf's output depends
deterministically on its rule count, so applying `AppendRule` across
generations nudges the population toward a target score. The demo
prints the seed's score, the best score per generation, and the final
evolved agent's change (rule count, rules).

Run with:
    uv run python examples/evolutionary_demo.py
"""

from __future__ import annotations

import asyncio
import random

from pydantic import BaseModel

from operad import (
    Agent,
    AppendRule,
    Configuration,
    Evolutionary,
    ExactMatch,
    evaluate,
)


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


class RuleCountMetric:
    """Scores predicted.value toward a target rule count (offline)."""

    name = "rule_count"

    def __init__(self, target: int) -> None:
        self.target = target

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        pv = getattr(predicted, "value", 0)
        return 1.0 - min(abs(pv - self.target), self.target) / self.target


async def main() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="demo",
        temperature=0.0,
        max_tokens=16,
    )

    seed = RuleCountLeaf(config=cfg)
    seed.rules = []
    await seed.abuild()

    dataset = [(Q(text=str(i)), R(value=3)) for i in range(5)]
    metric = RuleCountMetric(target=3)

    seed_report = await evaluate(seed, dataset, [metric])
    print(f"seed rule_count={len(seed.rules)}, score={seed_report.summary[metric.name]:.3f}")

    evo = Evolutionary(
        seed=seed,
        mutations=[AppendRule(path="", rule="be helpful")],
        metric=metric,
        dataset=dataset,
        population_size=6,
        generations=4,
        rng=random.Random(0),
    )
    best = await evo.run()

    best_report = await evaluate(best, dataset, [metric])
    print(f"best rule_count={len(best.rules)}, score={best_report.summary[metric.name]:.3f}")
    print("best.rules:")
    for i, r in enumerate(best.rules):
        print(f"  {i}: {r}")


if __name__ == "__main__":
    asyncio.run(main())
