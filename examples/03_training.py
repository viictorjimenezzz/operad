"""Example 3 - training: evolve `config.sampling.temperature` with MutationBeam.

What this script illustrates:

* a reference-free metric (length-band) used as the optimisation signal,
* `MutationBeam` proposing typed mutations on a single allowed op
  (`set_temperature`) and writing the winner back onto the seed in place,
* live observer output: per-generation candidate proposals, their LLM
  rationales, metric and judge scores, plus the temperature actually
  carried into the next generation,
* `agent.hash_content` shifting once the seed's config has been mutated.

Run modes:

    uv run python examples/03_training.py
    uv run python examples/03_training.py --offline
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from pydantic import BaseModel, Field

from operad import evaluate
from operad.agents import Reasoner
from operad.agents.reasoning.components import Critic
from operad.algorithms import MutationBeam
from operad.core.agent import Agent
from operad.core.config import Resilience, Sampling
from operad.runtime import set_limit
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import Event, registry

from _config import local_config, server_reachable
from utils import (
    LengthBandMetric,
    attach_dashboard,
    parse_dashboard_target,
    print_agent_card,
    print_dataset_table,
    print_mutation_generation,
    print_panel,
    print_rule,
    rich_available,
)

_RICH = rich_available()


_SCRIPT = "03_training"
DEFAULT_DASHBOARD = "127.0.0.1:7860"
_TARGET_LO, _TARGET_HI = 200, 450


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


class _LiveLogger:
    """Print each generation's candidate detail as soon as it is emitted."""

    def __init__(self, seed: Agent[Any, Any]) -> None:
        self._seed = seed
        self.history: list[dict[str, Any]] = []

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent) or event.kind != "generation":
            return
        gen_idx = int(event.payload.get("generation_index", -1))
        candidates = list(event.payload.get("candidates", []))
        selected = list(event.payload.get("selected_candidate_ids", []))
        temp_after = float(self._seed.config.sampling.temperature)
        print_mutation_generation(
            generation_index=gen_idx,
            candidates=candidates,
            selected_ids=selected,
            state_after=f"seed temperature after gen {gen_idx}: {temp_after:.2f}",
        )
        self.history.append(
            {"gen": gen_idx, "selected": selected, "temperature": temp_after}
        )


async def main(args: argparse.Namespace) -> None:
    if args.offline:
        print(
            f"[{_SCRIPT}] --offline: this example needs a real LLM; "
            "exiting 0 as no-op."
        )
        return

    attached = False
    if args.dashboard is not None:
        attached = attach_dashboard(
            args.dashboard,
            open_browser=not args.no_open,
            default=DEFAULT_DASHBOARD,
        )

    cfg = local_config(
        sampling=Sampling(temperature=0.0, max_tokens=1024),
        resilience=Resilience(max_retries=2, backoff_base=0.5, timeout=180.0),
    )
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} - start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)
    set_limit(backend=cfg.backend, host=cfg.host, concurrency=2)

    print_rule("Stage 1 - seed agent + dataset + metric")

    seed = Reasoner(
        config=cfg.model_copy(deep=True),
        input=Question,
        output=Answer,
        role="You answer science questions for a curious general reader.",
        task="Write a clear, factual answer.",
        rules=(
            "Use plain language; avoid jargon unless you define it.",
            "Cite at least one concrete example or mechanism.",
        ),
    )
    await seed.abuild()
    print_agent_card(seed, title="Seed agent")

    metric = LengthBandMetric(lo=_TARGET_LO, hi=_TARGET_HI, over_decay=300)
    dataset = [
        (Question(text="Why is the sky blue?"), Answer()),
        (Question(text="What causes ocean tides?"), Answer()),
    ]
    print_dataset_table(dataset, title="Eval dataset")
    print_panel(
        "Metric",
        (
            f"name:               {metric.name}\n"
            f"target band:        len(answer.text) in [{_TARGET_LO}, {_TARGET_HI}] chars\n"
            f"over-length decay:  {metric.over_decay} chars\n"
            "expected side:      empty (reference-free length scorer)"
        ),
    )

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])
    seed_temp = seed.config.sampling.temperature
    seed_hash = seed.hash_content
    sample_question = Question(text="Why is the sky blue?")
    seed_answer = (await seed(sample_question)).response.text

    print_panel(
        "Seed evaluation",
        (
            f"seed temperature:   {seed_temp:.2f}\n"
            f"seed length:        {len(seed_answer)} chars (target [{_TARGET_LO}, {_TARGET_HI}])\n"
            f"seed score:         {seed_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"sample answer:      {seed_answer[:200]}"
            + ("..." if len(seed_answer) > 200 else "")
        ),
    )

    print_rule("Stage 2 - MutationBeam (typed mutation proposals)")
    optimizer = MutationBeam(
        seed,
        metric=metric,
        dataset=dataset,
        allowed_mutations=["set_temperature"],
        branches_per_parent=args.branches,
        frontier_size=1,
        top_k=1,
        judge=Critic(config=cfg.model_copy(deep=True)),
        config=cfg.model_copy(deep=True),
    )
    await optimizer.abuild()
    print_panel(
        "Optimizer",
        (
            f"class:             {type(optimizer).__name__}\n"
            f"allowed_mutations: set_temperature\n"
            f"branches/parent:   {args.branches}\n"
            f"generations:       {args.generations}\n"
            f"frontier_size:     1\n"
            f"top_k:             1\n"
            "judge:             Critic (LLM-as-judge picks the strongest proposal)\n"
            "selection:         Beam + judge (top_k=1)"
        ),
    )

    print_rule("Stage 3 - fit (live per-generation candidate detail)")
    logger = _LiveLogger(seed)
    registry.register(logger)
    try:
        await optimizer.run(generations=args.generations)
    finally:
        registry.unregister(logger)

    print_rule("Stage 4 - final evaluation")
    final_report = await evaluate(seed, dataset, [metric])
    final_score = float(final_report.summary[metric.name])
    final_temp = seed.config.sampling.temperature
    final_hash = seed.hash_content
    final_answer = (await seed(sample_question)).response.text
    delta = final_score - seed_score
    delta_arrow = "+" if delta >= 0 else ""

    print_panel(
        "Result",
        (
            f"temperature:   {seed_temp:.2f}  ->  {final_temp:.2f}  "
            f"(delta {final_temp - seed_temp:+.2f})\n"
            f"answer length: {len(seed_answer)} chars  ->  {len(final_answer)} chars\n"
            f"score:         {seed_score:.3f}  ->  {final_score:.3f}  "
            f"({delta_arrow}{delta:.3f})\n"
            f"hash:          {seed_hash}\n"
            f"               -> {final_hash}\n"
            f"hash changed:  {seed_hash != final_hash} "
            f"(only `config.sampling.temperature` was mutated)\n\n"
            f"sample answer at final temperature:\n  {final_answer[:_TARGET_HI + 50]}"
            + ("..." if len(final_answer) > _TARGET_HI + 50 else "")
        ),
    )

    if attached:
        host, port = parse_dashboard_target(args.dashboard, default=DEFAULT_DASHBOARD)
        print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--generations", type=int, default=2)
    p.add_argument("--branches", type=int, default=4)
    p.add_argument(
        "--offline",
        action="store_true",
        help="No-op for verify.sh; this example needs a real LLM to run.",
    )
    p.add_argument(
        "--dashboard",
        nargs="?",
        const=DEFAULT_DASHBOARD,
        default=None,
        metavar="HOST:PORT",
        help="Attach to a running operad-dashboard server (default 127.0.0.1:7860).",
    )
    p.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the browser when --dashboard attaches.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
