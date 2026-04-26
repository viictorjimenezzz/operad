"""Example 4 — complex evolutionary training: mutate × Best-of-N per generation.

A real `Reasoner` answering science questions. The complexity here is
in the **optimiser**, not in the metric: a drop-in subclass of
`EvoGradient`, `EvoGradientBestOfN`, whose `step()` does three things
the default does not:

  1. **Mutation pool refresh.** Each generation builds a fresh pool of
     ops drawn from a per-generation strategy (rule-grow → rule-replace
     → rule-prune), so the search shifts focus over time.

  2. **BestOfN per individual.** Every mutated individual's fitness is
     measured by an inner Best-of-N: N independent samples per row from
     the agent; the metric scores each and the best wins. All inner
     calls across the population are launched in parallel, bounded by
     one global semaphore.

  3. **Top-K elitism.** Only the top-K individuals (not just the best)
     survive; they spawn the next generation's population.

The metric is a deterministic length-band score (no second LLM call)
so the loop wall time stays moderate against a local model. Watching
the per-generation table you see (a) score climbing, (b) survivors
converging, (c) the active mutation family shifting per generation.
The seed agent is a vanilla `Reasoner(...)` instance — no subclasses.

Run modes:

    uv run python examples/04_evolutionary_best_of_n.py            # hits the local llama-server
    uv run python examples/04_evolutionary_best_of_n.py --offline  # no-op for verify.sh
"""

from __future__ import annotations

import argparse
import asyncio
import random
import socket
import statistics
import sys
import time
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from operad import Agent, Configuration, evaluate
from operad.agents import Reasoner
from operad.core.config import Resilience, Sampling
from operad.metrics.base import MetricBase
from operad.optim import EvoGradient
from operad.runtime import set_limit
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import (
    Event,
    _enter_algorithm_run,
    emit_algorithm_event,
    registry,
)
from operad.utils.ops import AppendRule, DropRule, Op, ReplaceRule

from _config import local_config, server_reachable

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.table import Table

    _RICH = True
except ImportError:
    _RICH = False


_SCRIPT = "04_evolutionary_best_of_n"
DEFAULT_DASHBOARD = "127.0.0.1:7860"


# ---------------------------------------------------------------------------
# Domain.
# ---------------------------------------------------------------------------


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


# ---------------------------------------------------------------------------
# Reference-free length-band metric — fast (no LLM call) so we can afford
# many population × Best-of-N evaluations against a local model.
# ---------------------------------------------------------------------------


_TARGET_LO, _TARGET_HI = 250, 600


class _LengthBandMetric(MetricBase):
    """Score = 1.0 if `len(predicted.text) ∈ [LO, HI]`, decays linearly outside."""

    name = "length_band"

    async def score(self, predicted: BaseModel, expected: BaseModel) -> float:
        _ = expected
        text = str(getattr(predicted, "text", ""))
        n = len(text)
        if _TARGET_LO <= n <= _TARGET_HI:
            return 1.0
        if n < _TARGET_LO:
            return max(0.0, 0.99 * n / _TARGET_LO)
        over = n - _TARGET_HI
        return max(0.0, 1.0 - over / 400)


# ---------------------------------------------------------------------------
# Mini in-process Best-of-N: N parallel forwards per row, metric picks the best.
# ---------------------------------------------------------------------------


class _BestOfNInner:
    """N parallel forwards on the same agent; the metric picks the best."""

    def __init__(self, *, n: int, metric: MetricBase) -> None:
        if n < 1:
            raise ValueError("n must be >= 1")
        self.n = n
        self.metric = metric

    async def best_score(
        self, agent: Agent[Question, Answer], question: Question
    ) -> tuple[float, Answer]:
        attempts = await asyncio.gather(*(agent(question) for _ in range(self.n)))
        scored = [
            (await self.metric.score(a.response, Answer()), a.response)
            for a in attempts
        ]
        return max(scored, key=lambda p: p[0])


# ---------------------------------------------------------------------------
# Per-generation mutation strategies.
# ---------------------------------------------------------------------------


_RULE_BANK = [
    "Be concise.",
    "Cite at least one concrete example.",
    "Distinguish facts from opinions.",
    "Acknowledge uncertainty when present.",
    "Prefer plain language over jargon.",
    "Lead with the answer, then the reasoning.",
    "End with a single actionable next step.",
    "Avoid filler phrases such as 'in conclusion'.",
    "Use one short sentence per idea.",
    "Quote sources verbatim where relevant.",
]


def _mutations_for_generation(
    gen: int,
    survivors: list[Agent[Question, Answer]],
    rng: random.Random,
) -> list[Op]:
    """Per-generation mutation pool: the family rotates across generations.

    - gen 0: pure growth (AppendRule × 6)
    - gen 1: replacement (ReplaceRule × 4) + grow (AppendRule × 2)
    - gen 2: pruning (DropRule × 2) + targeted grow (AppendRule × 4)
    - gen 3+: small mixed pool focused on tail of the rule list
    """
    pool: list[Op] = []
    if gen == 0:
        pool = [AppendRule(path="", rule=r) for r in rng.sample(_RULE_BANK, k=6)]
    elif gen == 1:
        max_index = max(0, max(len(a.rules) for a in survivors) - 1)
        replacements = rng.sample(_RULE_BANK, k=4)
        pool = [
            ReplaceRule(path="", index=rng.randint(0, max_index), rule=r)
            for r in replacements
        ]
        pool += [AppendRule(path="", rule=r) for r in rng.sample(_RULE_BANK, k=2)]
    elif gen == 2:
        max_index = max(0, min(len(a.rules) for a in survivors) - 1)
        pool = [DropRule(path="", index=max_index) for _ in range(2)]
        pool += [AppendRule(path="", rule=r) for r in rng.sample(_RULE_BANK, k=4)]
    else:
        max_index = max(0, max(len(a.rules) for a in survivors) - 1)
        pool = [AppendRule(path="", rule=r) for r in rng.sample(_RULE_BANK, k=3)]
        pool += [
            ReplaceRule(path="", index=max_index, rule=rng.choice(_RULE_BANK))
            for _ in range(2)
        ]
    return pool


# ---------------------------------------------------------------------------
# The custom optimiser.
# ---------------------------------------------------------------------------


class EvoGradientBestOfN(EvoGradient):
    """`EvoGradient` with per-generation mutation refresh + BestOfN fitness.

    Public knobs added on top of the base class:
      - ``best_of_n``: number of inner stochastic forwards per row.
      - ``top_k``: how many survivors to keep at each generation.
      - ``concurrency``: global cap across all (individual × inner-N) calls.
    """

    def __init__(
        self,
        *args: Any,
        best_of_n: int = 2,
        top_k: int = 2,
        concurrency: int = 6,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if best_of_n < 1:
            raise ValueError("best_of_n must be >= 1")
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        self._best_of_n = best_of_n
        self._top_k = top_k
        self._concurrency = concurrency
        self._inner = _BestOfNInner(n=best_of_n, metric=self._metric)

    async def _evaluate_individual(
        self,
        agent: Agent[Question, Answer],
        sem: asyncio.Semaphore,
    ) -> float:
        async with sem:
            scores: list[float] = []
            for question, _ in self._dataset:
                s, _ = await self._inner.best_score(agent, question)
                scores.append(s)
            return statistics.fmean(scores) if scores else 0.0

    async def step(self) -> None:  # type: ignore[override]
        """One generation: refresh mutations → mutate → BestOfN → top-K."""
        if self._population is None:
            seed_score = await self._evaluate_individual(
                self._root, asyncio.Semaphore(self._concurrency)
            )
            self._last_scores = [seed_score]
            self._mutations = _mutations_for_generation(
                self._generation, [self._root], self._rng
            )
            self._population = list(
                await asyncio.gather(
                    *(
                        self._fresh_individual(self._root)
                        for _ in range(self._population_size)
                    )
                )
            )

        self._mutations = _mutations_for_generation(
            self._generation, self._population, self._rng
        )

        sem = asyncio.Semaphore(self._concurrency)
        scores = list(
            await asyncio.gather(
                *(self._evaluate_individual(a, sem) for a in self._population)
            )
        )
        ranked = sorted(range(self._population_size), key=lambda i: -scores[i])
        survivor_indices = ranked[: self._top_k]
        survivors = [self._population[i] for i in survivor_indices]

        await self._emit_extended_event(
            scores=scores,
            survivor_indices=survivor_indices,
            mutation_family=self._family_label(),
        )

        refills_needed = self._population_size - len(survivors)
        refill_parents = [
            survivors[i % len(survivors)] for i in range(refills_needed)
        ]
        refills = list(
            await asyncio.gather(
                *(self._fresh_individual(p) for p in refill_parents)
            )
        )
        new_population = survivors + refills
        kept_ids = {id(a) for a in new_population}
        self._origin_ops = {
            k: v for k, v in self._origin_ops.items() if k in kept_ids
        }
        self._population = new_population

        best = survivors[0]
        await self._write_back(best)
        self._last_scores = scores
        self._generation += 1

    def _family_label(self) -> str:
        return ", ".join(sorted({op.name for op in self._mutations}))

    async def _emit_extended_event(
        self,
        *,
        scores: list[float],
        survivor_indices: list[int],
        mutation_family: str,
    ) -> None:
        baseline = self._last_scores or []
        median = statistics.median(baseline) if baseline else float("-inf")
        ops = [self._origin_ops.get(id(a), "identity") for a in self._population]
        improved = [s > median for s in scores]
        attempt_counts: dict[str, int] = {}
        success_counts: dict[str, int] = {}
        for i, op_name in enumerate(ops):
            attempt_counts[op_name] = attempt_counts.get(op_name, 0) + 1
            if improved[i]:
                success_counts[op_name] = success_counts.get(op_name, 0) + 1
        payload = {
            "gen_index": self._generation,
            "population_scores": scores,
            "survivor_indices": list(survivor_indices),
            "mutations": [
                {
                    "individual_id": i,
                    "op": ops[i],
                    "improved": bool(improved[i]),
                }
                for i in range(len(self._population))
            ],
            "op_attempt_counts": attempt_counts,
            "op_success_counts": success_counts,
            "mutation_family": mutation_family,
            "best_of_n": self._best_of_n,
            "top_k": self._top_k,
        }
        with _enter_algorithm_run():
            await emit_algorithm_event(
                "generation",
                algorithm_path=type(self).__name__,
                payload=payload,
            )


# ---------------------------------------------------------------------------
# Per-generation observer for the Rich table.
# ---------------------------------------------------------------------------


class _GenerationLogger:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent) or event.kind != "generation":
            return
        scores = event.payload.get("population_scores", [])
        self.rows.append(
            {
                "gen": event.payload.get("gen_index", -1),
                "best": max(scores) if scores else None,
                "mean": statistics.fmean(scores) if scores else None,
                "spread": (max(scores) - min(scores)) if scores else None,
                "family": event.payload.get("mutation_family", "?"),
                "best_of_n": event.payload.get("best_of_n", "?"),
                "top_k": event.payload.get("top_k", "?"),
                "survivors": event.payload.get("survivor_indices", []),
            }
        )


# ---------------------------------------------------------------------------
# Pretty terminal output.
# ---------------------------------------------------------------------------


def _rule(title: str) -> None:
    if _RICH:
        Console(width=140).rule(f"[bold cyan]{title}")
    else:
        bar = "═" * (len(title) + 6)
        print(f"\n{bar}\n   {title}\n{bar}")


def _panel(title: str, body: str) -> None:
    if _RICH:
        Console(width=140).print(Panel(body, title=title, border_style="cyan"))
    else:
        bar = "─" * 60
        print(f"\n{bar}\n{title}\n{bar}\n{body}\n{bar}")


def _print_generations(logger: _GenerationLogger) -> None:
    if not _RICH:
        print("gen | family                                  | best  | mean  | spread | survivors")
        for r in logger.rows:
            print(
                f"  {r['gen']:>2} | {r['family'][:38]:>38} | "
                f"{r['best']:.3f} | {r['mean']:.3f} | {r['spread']:.3f} | {r['survivors']}"
            )
        return
    table = Table(
        title="Per-generation training (mutation × Best-of-N)",
        border_style="cyan",
    )
    table.add_column("gen", justify="right")
    table.add_column("active mutation family", justify="left")
    table.add_column("BoN", justify="right")
    table.add_column("top-K", justify="right")
    table.add_column("best", justify="right")
    table.add_column("mean", justify="right")
    table.add_column("spread", justify="right")
    table.add_column("survivors", justify="left")
    for r in logger.rows:
        table.add_row(
            str(r["gen"]),
            r["family"],
            str(r["best_of_n"]),
            str(r["top_k"]),
            f"{r['best']:.3f}",
            f"{r['mean']:.3f}",
            f"{r['spread']:.3f}",
            str(r["survivors"]),
        )
    Console(width=140).print(table)


def _parse_dashboard_target(value: str) -> tuple[str, int]:
    raw = value or DEFAULT_DASHBOARD
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urlparse(raw)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7860
    return host, port


def _server_up(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _attach_dashboard(target: str, *, open_browser: bool = True) -> bool:
    host, port = _parse_dashboard_target(target)
    if not _server_up(host, port):
        print(
            f"[dashboard] no server at {host}:{port} — "
            "start one with `operad-dashboard --port 7860` then re-run with --dashboard"
        )
        return False
    from operad.dashboard import attach

    attach(host=host, port=port)
    url = f"http://{host}:{port}"
    print(f"[dashboard] attached → {url}")
    if open_browser:
        try:
            import webbrowser

            webbrowser.open_new_tab(url)
        except Exception:
            pass
    return True


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    if args.offline:
        print(
            f"[{_SCRIPT}] --offline: this example needs a real LLM; "
            "exiting 0 as no-op."
        )
        return
    attached = False
    if args.dashboard is not None:
        attached = _attach_dashboard(args.dashboard, open_browser=not args.no_open)

    cfg = local_config(
        sampling=Sampling(temperature=0.7, max_tokens=1024),
        resilience=Resilience(max_retries=2, backoff_base=0.5, timeout=180.0),
    )
    print(
        f"[{_SCRIPT}] backend={cfg.backend} host={cfg.host} model={cfg.model}"
    )
    if not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} — start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)
    # Bound parallel calls so the local llama-server is not overwhelmed.
    set_limit(backend=cfg.backend, host=cfg.host, concurrency=3)

    _rule("Stage 1 — assemble seed agent + dataset + metric")

    seed = Reasoner(
        config=cfg.model_copy(deep=True),
        input=Question,
        output=Answer,
        role="You answer science questions for a curious general reader.",
        task="Write a clear, factual answer.",
        rules=("Be helpful.",),  # weak seed — mutations grow this list
    )
    await seed.abuild()

    metric = _LengthBandMetric()

    dataset = [
        (Question(text="Why are bees important?"), Answer()),
        (Question(text="What is climate change?"), Answer()),
        (Question(text="Define photosynthesis."), Answer()),
    ]

    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])
    seed_hash = seed.hash_content
    seed_text = (await seed(Question(text="Why are bees important?"))).response.text

    _panel(
        "Seed",
        (
            f"agent class:        {type(seed).__name__}\n"
            f"role:               {seed.role!r}\n"
            f"rules:              {seed.rules}\n"
            f"metric:             reference-free length-band score\n"
            f"seed score:         {seed_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"sample answer:      {seed_text[:200]}"
            + ("…" if len(seed_text) > 200 else "")
        ),
    )

    _rule("Stage 2 — wire EvoGradientBestOfN")
    optimizer = EvoGradientBestOfN(
        list(seed.parameters()),
        # `_mutations` is replaced every step; this seed pool is overwritten.
        mutations=[AppendRule(path="", rule="placeholder")],
        metric=metric,
        dataset=dataset,
        population_size=args.population,
        rng=random.Random(0),
        best_of_n=args.best_of_n,
        top_k=args.top_k,
        concurrency=args.concurrency,
    )
    _panel(
        "Optimizer",
        (
            f"class:           {type(optimizer).__name__}\n"
            f"population:      {args.population}\n"
            f"best_of_n:       {args.best_of_n}      (inner stochastic samples per row)\n"
            f"top_k:           {args.top_k}      (survivors carried into the next generation)\n"
            f"concurrency:     {args.concurrency}      (global cap across all (individual × N) calls)\n"
            "rng seed:        0\n\n"
            "Mutation strategy (cycles per generation):\n"
            "  gen 0:  AppendRule × 6\n"
            "  gen 1:  ReplaceRule × 4 + AppendRule × 2\n"
            "  gen 2:  DropRule × 2 + AppendRule × 4\n"
            "  gen 3+: AppendRule × 3 + ReplaceRule × 2 (tail-focused)"
        ),
    )

    _rule(f"Stage 3 — fit ({args.generations} generations)")
    logger = _GenerationLogger()
    registry.register(logger)

    started = time.time()
    if _RICH:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]gen {task.fields[gen]}/{task.total}"),
            BarColumn(),
            TextColumn("best={task.fields[best]:.3f}"),
            TimeElapsedColumn(),
            transient=False,
        ) as progress:
            task = progress.add_task(
                "evolving", total=args.generations, gen=0, best=0.0
            )
            for gen_index in range(args.generations):
                await optimizer.step()
                last = logger.rows[-1] if logger.rows else {}
                progress.update(
                    task,
                    advance=1,
                    gen=gen_index + 1,
                    best=last.get("best", 0.0),
                )
    else:
        for gen_index in range(args.generations):
            await optimizer.step()
            last = logger.rows[-1] if logger.rows else {}
            print(
                f"  gen {gen_index + 1}/{args.generations}  "
                f"best={last.get('best', 0.0):.3f}"
            )
    elapsed = time.time() - started
    registry.unregister(logger)

    _print_generations(logger)

    _rule("Stage 4 — final evaluation")
    final_report = await evaluate(seed, dataset, [metric])
    final_score = float(final_report.summary[metric.name])
    final_hash = seed.hash_content
    final_text = (
        await seed(Question(text="Why are bees important?"))
    ).response.text

    _panel(
        "Result",
        (
            f"seed score:    {seed_score:.3f}    →  final: {final_score:.3f}\n"
            f"seed hash:     {seed_hash}\n"
            f"final hash:    {final_hash}\n"
            f"hash changed:  {seed_hash != final_hash}\n"
            f"wall time:     {elapsed:.1f}s for {args.generations} generations × "
            f"{args.population} × Best-of-{args.best_of_n}\n\n"
            f"final rules:   {seed.rules}\n"
            f"sample answer at final state:\n  {final_text[:300]}"
            + ("…" if len(final_text) > 300 else "")
        ),
    )
    if attached:
        host, port = _parse_dashboard_target(args.dashboard)
        print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )

    # Intentionally NO assert on seed_score vs final_score — a real LLM
    # judge is noisy. The per-generation table is what shows the
    # optimiser working: best-per-gen climbs across generations.


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--generations", type=int, default=3)
    p.add_argument("--population", type=int, default=4)
    p.add_argument("--top-k", dest="top_k", type=int, default=2)
    p.add_argument("--best-of-n", dest="best_of_n", type=int, default=2)
    p.add_argument("--concurrency", type=int, default=6)
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
