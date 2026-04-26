"""Example 4 - evolutionary: richer MutationBeam search over prompt mutations.

What this script illustrates:

* a `Reasoner` whose `rules` list is the trainable surface,
* `MutationBeam` proposing typed prompt mutations across three ops -
  `append_rule`, `replace_rule`, `drop_rule` - with a Critic LLM judge
  picking survivors,
* live observer output: each generation's candidate proposals (with the
  LLM's rationale, metric and judge scores, and which one was selected)
  plus the surviving agent's `rules` after write-back,
* a final rules diff showing exactly which prompt changes won.

Run modes:

    uv run python examples/04_evolutionary.py
    uv run python examples/04_evolutionary.py --offline
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
    print_rules_diff,
    rich_available,
)

_RICH = rich_available()


_SCRIPT = "04_evolutionary"
DEFAULT_DASHBOARD = "127.0.0.1:7860"
_TARGET_LO, _TARGET_HI = 250, 600


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


class _LiveLogger:
    """Print each generation's candidate detail and the surviving rules."""

    def __init__(self, seed: Agent[Any, Any]) -> None:
        self._seed = seed
        self.history: list[dict[str, Any]] = []

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent) or event.kind != "generation":
            return
        gen_idx = int(event.payload.get("generation_index", -1))
        candidates = list(event.payload.get("candidates", []))
        selected = list(event.payload.get("selected_candidate_ids", []))
        rules_after = list(self._seed.rules)
        rules_preview = "; ".join(rules_after) if rules_after else "(no rules)"
        if len(rules_preview) > 110:
            rules_preview = rules_preview[:107] + "..."
        print_mutation_generation(
            generation_index=gen_idx,
            candidates=candidates,
            selected_ids=selected,
            state_after=f"seed.rules ({len(rules_after)}): {rules_preview}",
        )
        self.history.append(
            {"gen": gen_idx, "selected": selected, "rules": rules_after}
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
        sampling=Sampling(temperature=0.7, max_tokens=1024),
        resilience=Resilience(max_retries=2, backoff_base=0.5, timeout=180.0),
    )
    print(f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}")
    if not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} - start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)

    set_limit(backend=cfg.backend, host=cfg.host, concurrency=3)

    print_rule("Stage 1 - seed agent + dataset + metric")

    seed = Reasoner(
        config=cfg.model_copy(deep=True),
        input=Question,
        output=Answer,
        role="You answer science questions for a curious general reader.",
        task="Write a clear, factual answer.",
        rules=("Be helpful.",),
    )
    await seed.abuild()
    print_agent_card(seed, title="Seed agent")

    metric = LengthBandMetric(lo=_TARGET_LO, hi=_TARGET_HI, over_decay=400)
    dataset = [
        (Question(text="Why are bees important?"), Answer()),
        (Question(text="What is climate change?"), Answer()),
        (Question(text="Define photosynthesis."), Answer()),
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

    seed_rules_before = list(seed.rules)

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])
    seed_hash = seed.hash_content
    seed_text = (await seed(Question(text="Why are bees important?"))).response.text

    print_panel(
        "Seed evaluation",
        (
            f"role:               {seed.role!r}\n"
            f"rules:              {seed_rules_before}\n"
            f"seed score:         {seed_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"sample answer:      {seed_text[:200]}"
            + ("..." if len(seed_text) > 200 else "")
        ),
    )

    print_rule("Stage 2 - MutationBeam setup")
    optimizer = MutationBeam(
        seed,
        metric=metric,
        dataset=dataset,
        allowed_mutations=["append_rule", "replace_rule", "drop_rule"],
        branches_per_parent=args.branches,
        frontier_size=args.frontier,
        top_k=args.top_k,
        judge=Critic(config=cfg.model_copy(deep=True)),
        config=cfg.model_copy(deep=True),
    )
    await optimizer.abuild()

    print_panel(
        "Optimizer",
        (
            f"class:             {type(optimizer).__name__}\n"
            f"generations:       {args.generations}\n"
            f"branches/parent:   {args.branches}\n"
            f"frontier_size:     {args.frontier}\n"
            f"top_k:             {args.top_k}\n"
            "allowed_mutations: append_rule, replace_rule, drop_rule\n"
            "judge:             Critic (LLM picks the strongest proposal)\n"
            "selection:         Beam + judge (best is written back onto seed)"
        ),
    )

    print_rule(f"Stage 3 - evolve ({args.generations} generations)")
    logger = _LiveLogger(seed)
    registry.register(logger)
    try:
        await optimizer.run(generations=args.generations)
    finally:
        registry.unregister(logger)

    print_rule("Stage 4 - final evaluation")
    final_report = await evaluate(seed, dataset, [metric])
    final_score = float(final_report.summary[metric.name])
    final_hash = seed.hash_content
    final_text = (await seed(Question(text="Why are bees important?"))).response.text
    delta = final_score - seed_score
    delta_arrow = "+" if delta >= 0 else ""

    print_rules_diff(seed_rules_before, list(seed.rules), title="Rules: seed -> final")

    print_panel(
        "Result",
        (
            f"score:        {seed_score:.3f}  ->  {final_score:.3f}  "
            f"({delta_arrow}{delta:.3f})\n"
            f"answer len:   {len(seed_text)} chars  ->  {len(final_text)} chars\n"
            f"hash:         {seed_hash}\n"
            f"              -> {final_hash}\n"
            f"hash changed: {seed_hash != final_hash} "
            f"(`role`/`task` are pinned; only `rules` was mutated)\n\n"
            f"final rules:  {list(seed.rules)}\n"
            f"sample answer at final state:\n  {final_text[:300]}"
            + ("..." if len(final_text) > 300 else "")
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
    p.add_argument("--generations", type=int, default=3)
    p.add_argument("--branches", type=int, default=4)
    p.add_argument("--frontier", type=int, default=3)
    p.add_argument("--top-k", dest="top_k", type=int, default=3)
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
