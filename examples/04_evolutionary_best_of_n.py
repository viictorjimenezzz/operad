"""Example 4 - evolutionary: richer MutationBeam search over prompt mutations.

Run modes:

    uv run python examples/04_evolutionary_best_of_n.py
    uv run python examples/04_evolutionary_best_of_n.py --offline
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
from operad.core.config import Resilience, Sampling
from operad.runtime import set_limit
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import Event, registry

from _config import local_config, server_reachable
from utils import (
    LengthBandMetric,
    attach_dashboard,
    op_histogram,
    parse_dashboard_target,
    print_panel,
    print_rule,
    rich_available,
    score_stats,
)

try:
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table

    _RICH = rich_available()
except ImportError:
    _RICH = False


_SCRIPT = "04_evolutionary_best_of_n"
DEFAULT_DASHBOARD = "127.0.0.1:7860"
_TARGET_LO, _TARGET_HI = 250, 600


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


class _GenerationLogger:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent) or event.kind != "generation":
            return
        candidates = event.payload.get("candidates", [])
        metric_scores = [float(c.get("metric_score", 0.0)) for c in candidates]
        judge_scores = [
            float(c["score"])
            for c in candidates
            if c.get("score") is not None
        ]
        best, mean, spread = score_stats(metric_scores)
        judge_best = max(judge_scores) if judge_scores else 0.0
        self.rows.append(
            {
                "gen": int(event.payload.get("generation_index", -1)),
                "best": best,
                "mean": mean,
                "spread": spread,
                "judge_best": judge_best,
                "ops": [str(c.get("op", "")) for c in candidates],
                "selected": list(event.payload.get("selected_candidate_ids", [])),
            }
        )


def _print_generations(logger: _GenerationLogger) -> None:
    if not _RICH:
        print("gen | best | mean | spread | judge_best | ops | selected")
        for row in logger.rows:
            print(
                f"  {row['gen']:>2} | {row['best']:.3f} | {row['mean']:.3f} | "
                f"{row['spread']:.3f} | {row['judge_best']:.3f} | "
                f"{op_histogram(row['ops'])} | {row['selected']}"
            )
        return

    table = Table(title="Evolution generations (MutationBeam)", border_style="cyan")
    table.add_column("gen", justify="right")
    table.add_column("best", justify="right")
    table.add_column("mean", justify="right")
    table.add_column("spread", justify="right")
    table.add_column("judge_best", justify="right")
    table.add_column("ops", justify="left")
    table.add_column("selected", justify="left")
    for row in logger.rows:
        table.add_row(
            str(row["gen"]),
            f"{row['best']:.3f}",
            f"{row['mean']:.3f}",
            f"{row['spread']:.3f}",
            f"{row['judge_best']:.3f}",
            op_histogram(row["ops"]),
            str(row["selected"]),
        )
    Console(width=140).print(table)


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

    metric = LengthBandMetric(lo=_TARGET_LO, hi=_TARGET_HI, over_decay=400)
    dataset = [
        (Question(text="Why are bees important?"), Answer()),
        (Question(text="What is climate change?"), Answer()),
        (Question(text="Define photosynthesis."), Answer()),
    ]

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])
    seed_hash = seed.hash_content
    seed_text = (await seed(Question(text="Why are bees important?"))).response.text

    print_panel(
        "Seed",
        (
            f"agent class:        {type(seed).__name__}\n"
            f"role:               {seed.role!r}\n"
            f"rules:              {seed.rules}\n"
            f"metric:             reference-free length-band score\n"
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
            "selection:         Beam + judge"
        ),
    )

    print_rule(f"Stage 3 - evolve ({args.generations} generations)")
    logger = _GenerationLogger()
    registry.register(logger)

    if _RICH:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]gen {task.fields[gen]}/{task.total}"),
            BarColumn(),
            TextColumn("best={task.fields[best]:.3f}"),
            TimeElapsedColumn(),
            transient=False,
        ) as progress:
            task = progress.add_task("evolving", total=args.generations, gen=0, best=0.0)
            await optimizer.run(generations=args.generations)
            for row in logger.rows:
                progress.update(
                    task,
                    advance=1,
                    gen=row["gen"] + 1,
                    best=row["best"],
                )
    else:
        await optimizer.run(generations=args.generations)
        for row in logger.rows:
            print(
                f"  gen {row['gen'] + 1}/{args.generations}  best={row['best']:.3f}"
            )

    registry.unregister(logger)
    _print_generations(logger)

    print_rule("Stage 4 - final evaluation")
    final_report = await evaluate(seed, dataset, [metric])
    final_score = float(final_report.summary[metric.name])
    final_hash = seed.hash_content
    final_text = (await seed(Question(text="Why are bees important?"))).response.text

    print_panel(
        "Result",
        (
            f"seed score:    {seed_score:.3f}  ->  final: {final_score:.3f}\n"
            f"seed hash:     {seed_hash}\n"
            f"final hash:    {final_hash}\n"
            f"hash changed:  {seed_hash != final_hash}\n\n"
            f"final rules:   {seed.rules}\n"
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
