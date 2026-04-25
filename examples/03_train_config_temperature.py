"""Example 3 — training: tune config-related parameters across epochs.

A `Reasoner` whose `config.sampling.temperature` is the trainable knob.
The metric rewards answers whose length lands in a target band; the
deterministic offline forward maps temperature monotonically to length,
so the optimiser visibly climbs from a cold seed (T=0.0, too short) to
a temperature in the warm-but-not-loose band that maximises score.

The training loop is `EvoGradient` driven by a custom `SetTemperature`
mutation pool (six values across [0.0, 1.0]). Each generation:

  1. Mutates every survivor with a random `SetTemperature(...)` op.
  2. Builds + evaluates every individual on the validation set.
  3. Keeps the top half; refills by re-mutating the survivors.

Per-generation rows are printed to a Rich table; the seed-vs-final
hash and temperature are highlighted at the end. No LLM, no network.

Run modes:

    uv run python examples/03_train_config_temperature.py            # offline (default)
    uv run python examples/03_train_config_temperature.py --offline  # parity flag for verify.sh
"""

from __future__ import annotations

import argparse
import asyncio
import random
from typing import Any

from pydantic import BaseModel, Field

from operad import Agent, Configuration, evaluate
from operad.core.config import Sampling
from operad.metrics.base import MetricBase
from operad.optim import EvoGradient
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import Event, registry
from operad.utils.ops import SetTemperature

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


# ---------------------------------------------------------------------------
# Domain.
# ---------------------------------------------------------------------------


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


# ---------------------------------------------------------------------------
# Offline leaf: deterministic length as a function of temperature.
# ---------------------------------------------------------------------------


_BANK = [
    "Bees pollinate.",
    "Bees pollinate flowering plants.",
    "Bees pollinate flowering plants and crops worldwide.",
    "Bees pollinate flowering plants and crops, sustaining global food production.",
    (
        "Bees pollinate flowering plants and crops, sustaining global food "
        "production for humans and many wildlife species."
    ),
    (
        "Bees pollinate flowering plants and crops, sustaining global food "
        "production for humans and many wildlife species. Their decline "
        "ripples through every layer of the trophic pyramid."
    ),
    (
        "Bees pollinate flowering plants and crops, sustaining global food "
        "production for humans and many wildlife species. Their decline "
        "ripples through every layer of the trophic pyramid; rebuilding "
        "wildflower corridors, banning the most damaging pesticides, and "
        "supporting commercial keepers are the three highest-leverage moves."
    ),
    (
        "Bees pollinate flowering plants and crops, sustaining global food "
        "production for humans and many wildlife species. Their decline "
        "ripples through every layer of the trophic pyramid; rebuilding "
        "wildflower corridors, banning the most damaging pesticides, and "
        "supporting commercial keepers are the three highest-leverage moves. "
        "Each of those, in turn, requires coordinated action across the "
        "agricultural, regulatory, and economic layers of modern food systems."
    ),
]


def _length_for_temperature(t: float) -> int:
    """Pick which `_BANK` entry to return: temperature monotonically grows length.

    Maps `t in [0, 1]` to an integer index in `[0, len(_BANK) - 1]` via a
    simple linear scaling. Deterministic — required for an offline demo.
    """
    bucket = int(round(t * (len(_BANK) - 1)))
    return max(0, min(len(_BANK) - 1, bucket))


class _LengthControlledLeaf(Agent[Question, Answer]):
    """Offline leaf: output length grows with `config.sampling.temperature`.

    The base `Agent.forward` would call strands; here we override it to
    pick a canned answer of an appropriate length so the optimiser has a
    visible signal across temperatures.
    """

    input = Question
    output = Answer

    async def forward(self, x: Question) -> Answer:  # type: ignore[override]
        t = self.config.sampling.temperature if self.config else 0.0
        return Answer(text=_BANK[_length_for_temperature(t)])


# ---------------------------------------------------------------------------
# Metric: target a length band of [120, 200] characters.
# ---------------------------------------------------------------------------


_TARGET_LO, _TARGET_HI = 100, 200


class _LengthBandMetric(MetricBase):
    """Reward answers whose length lands in `[_TARGET_LO, _TARGET_HI]`.

    Score is 1.0 inside the band, decays linearly outside it. Reference-
    free — `expected` is unused.
    """

    name = "length_band"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        text = str(getattr(predicted, "text", ""))
        n = len(text)
        if _TARGET_LO <= n <= _TARGET_HI:
            return 1.0
        if n < _TARGET_LO:
            # Linear from 0.0 at length 0 to 0.99 just under _TARGET_LO.
            return max(0.0, 0.99 * n / _TARGET_LO)
        # Symmetric decay above the band.
        over = n - _TARGET_HI
        return max(0.0, 1.0 - over / 200)


# ---------------------------------------------------------------------------
# Per-generation observer: collects rows for the final table.
# ---------------------------------------------------------------------------


class _GenerationLogger:
    """Capture one row per `generation` AlgorithmEvent."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent) or event.kind != "generation":
            return
        scores = event.payload.get("population_scores", [])
        ops = [m["op"] for m in event.payload.get("mutations", [])]
        self.rows.append(
            {
                "gen": event.payload.get("gen_index", -1),
                "best": max(scores) if scores else None,
                "mean": sum(scores) / len(scores) if scores else None,
                "spread": (max(scores) - min(scores)) if scores else None,
                "ops": ops,
                "survivors": event.payload.get("survivor_indices", []),
            }
        )


# ---------------------------------------------------------------------------
# Pretty terminal output.
# ---------------------------------------------------------------------------


def _rule(title: str) -> None:
    if _RICH:
        Console(width=120).rule(f"[bold cyan]{title}")
    else:
        bar = "═" * (len(title) + 6)
        print(f"\n{bar}\n   {title}\n{bar}")


def _panel(title: str, body: str) -> None:
    if _RICH:
        Console(width=120).print(Panel(body, title=title, border_style="cyan"))
    else:
        bar = "─" * 60
        print(f"\n{bar}\n{title}\n{bar}\n{body}\n{bar}")


def _print_generation_table(logger: _GenerationLogger) -> None:
    if not _RICH:
        print("\ngen | best | mean | spread | survivors")
        for r in logger.rows:
            print(
                f"  {r['gen']:>2} | "
                f"{r['best']:.3f} | {r['mean']:.3f} | {r['spread']:.3f} | "
                f"{r['survivors']}"
            )
        return
    table = Table(title="Per-generation training report", border_style="cyan")
    table.add_column("gen", justify="right")
    table.add_column("best", justify="right")
    table.add_column("mean", justify="right")
    table.add_column("spread", justify="right")
    table.add_column("ops applied this gen", justify="left")
    table.add_column("survivors", justify="left")
    for r in logger.rows:
        # Op histogram in this generation.
        op_counts: dict[str, int] = {}
        for op in r["ops"]:
            op_counts[op] = op_counts.get(op, 0) + 1
        ops_str = ", ".join(f"{k}×{v}" for k, v in sorted(op_counts.items()))
        table.add_row(
            str(r["gen"]),
            f"{r['best']:.3f}",
            f"{r['mean']:.3f}",
            f"{r['spread']:.3f}",
            ops_str,
            str(r["survivors"]),
        )
    Console(width=120).print(table)


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


_OFFLINE_CFG = Configuration(
    backend="llamacpp",
    host="127.0.0.1:0",
    model="offline-stub",
    sampling=Sampling(temperature=0.0, max_tokens=2048),
)


async def main(args: argparse.Namespace) -> None:
    _ = args  # demo runs offline unconditionally

    _rule("Stage 1 — assemble seed agent + dataset + metric")
    seed = _LengthControlledLeaf(config=_OFFLINE_CFG.model_copy(deep=True))
    # Mark only the temperature trainable so the optimiser narrows on it.
    seed.mark_trainable(temperature=True)
    await seed.abuild()

    dataset = [
        (Question(text="Why are bees important?"), Answer())
        for _ in range(5)
    ]
    metric = _LengthBandMetric()

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])
    seed_temp = seed.config.sampling.temperature
    seed_text = (await seed(Question(text="Why are bees important?"))).response.text
    seed_hash = seed.hash_content

    _panel(
        "Seed",
        (
            f"agent class:        {type(seed).__name__}\n"
            f"trainable:          config.sampling.temperature\n"
            f"target length band: [{_TARGET_LO}, {_TARGET_HI}] chars\n"
            f"seed temperature:   {seed_temp:.2f}\n"
            f"seed length:        {len(seed_text)} chars\n"
            f"seed score:         {seed_score:.3f}\n"
            f"seed hash:          {seed_hash}"
        ),
    )

    _rule("Stage 2 — build EvoGradient with SetTemperature mutations")
    mutations = [
        SetTemperature(path="", temperature=0.0),
        SetTemperature(path="", temperature=0.2),
        SetTemperature(path="", temperature=0.4),
        SetTemperature(path="", temperature=0.6),
        SetTemperature(path="", temperature=0.8),
        SetTemperature(path="", temperature=1.0),
    ]
    optimizer = EvoGradient(
        list(seed.parameters()),
        mutations=mutations,
        metric=metric,
        dataset=dataset,
        population_size=6,
        rng=random.Random(0),
    )
    _panel(
        "Optimizer",
        (
            f"class:            {type(optimizer).__name__}\n"
            f"population_size:  6\n"
            f"mutation pool:    {len(mutations)} × SetTemperature ∈ "
            "{0.0, 0.2, 0.4, 0.6, 0.8, 1.0}\n"
            "rng seed:         0"
        ),
    )

    _rule("Stage 3 — fit (4 generations)")
    logger = _GenerationLogger()
    registry.register(logger)
    try:
        for _ in range(4):
            await optimizer.step()
    finally:
        registry.unregister(logger)

    _print_generation_table(logger)

    _rule("Stage 4 — final evaluation")
    final_report = await evaluate(seed, dataset, [metric])
    final_score = float(final_report.summary[metric.name])
    final_temp = seed.config.sampling.temperature
    final_text = (await seed(Question(text="Why are bees important?"))).response.text
    final_hash = seed.hash_content

    _panel(
        "Result",
        (
            f"seed temperature:   {seed_temp:.2f}     →  final: {final_temp:.2f}\n"
            f"seed length:        {len(seed_text)} chars  →  final: {len(final_text)} chars\n"
            f"seed score:         {seed_score:.3f}    →  final: {final_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"final hash:         {final_hash}\n"
            f"hash changed:       {seed_hash != final_hash}\n\n"
            f"final answer (length {len(final_text)}):\n  {final_text[:_TARGET_HI + 30]}"
            + ("…" if len(final_text) > _TARGET_HI + 30 else "")
        ),
    )

    assert final_score + 1e-9 >= seed_score, (
        f"score regressed: seed={seed_score} final={final_score}"
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--offline",
        action="store_true",
        help="Parity flag for verify.sh; the demo always runs offline.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
