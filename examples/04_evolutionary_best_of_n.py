"""Example 4 — complex evolutionary training: mutate × Best-of-N per generation.

Drop-in subclass of `EvoGradient` whose `step()` does three things the
default does not:

  1. **Mutation pool refresh.** Each generation builds a fresh pool of ops
     by walking the current survivors — newer survivors propose new ops
     drawn from a per-generation strategy (rule-grow, then rule-replace,
     then rule-prune in rotation). The pool size and op family change
     across generations, so the search shifts focus over time.

  2. **BestOfN per individual.** Every mutated individual's fitness is
     measured by running an inner *Best-of-N* sampler against the dataset:
     N stochastic outputs per row, the inner judge picks the best, the
     metric averages across rows. All BestOfN runs across all individuals
     run **in parallel** under one global semaphore.

  3. **Top-K elitism.** Only the top-K individuals (not just the best)
     survive; they spawn the next generation's pool. K shrinks across
     generations to tighten the search.

The scenario: train an offline `Reasoner` whose answer length, lexical
density, and rule count jointly determine its score. The seed has a
weak role + minimal rules; the optimiser climbs by appending and
swapping rules. Watching the per-generation table you see (a) score
climbing, (b) survivors converging, (c) the active mutation family
shifting per generation.

Run modes:

    uv run python examples/04_evolutionary_best_of_n.py            # offline (default)
    uv run python examples/04_evolutionary_best_of_n.py --offline  # parity flag for verify.sh
    uv run python examples/04_evolutionary_best_of_n.py --generations 6
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import random
import statistics
import time
from typing import Any

from pydantic import BaseModel, Field

from operad import Agent, Configuration, evaluate
from operad.core.config import Sampling
from operad.metrics.base import MetricBase
from operad.optim import EvoGradient
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import (
    Event,
    _enter_algorithm_run,
    emit_algorithm_event,
    registry,
)
from operad.utils.errors import BuildError
from operad.utils.ops import AppendRule, DropRule, Op, ReplaceRule

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


# ---------------------------------------------------------------------------
# Domain.
# ---------------------------------------------------------------------------


class Question(BaseModel):
    text: str = Field(default="", description="A short user question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


# ---------------------------------------------------------------------------
# Offline leaf: deterministic answer composed from role + rules.
# ---------------------------------------------------------------------------


class _RoleRulesLeaf(Agent[Question, Answer]):
    """Offline leaf whose output is `role` followed by the joined `rules`.

    Behaviour is fully a function of declared state, so applying ops
    visibly changes the answer. No LLM, no network.
    """

    input = Question
    output = Answer

    async def forward(self, x: Question) -> Answer:  # type: ignore[override]
        # `model_construct`-built sentinels lack attributes; default safely.
        _ = getattr(x, "text", "")
        body = self.role + ". "
        if self.rules:
            body += " · ".join(self.rules) + "."
        return Answer(text=body)


# ---------------------------------------------------------------------------
# Metric: rewards (a) length-in-band, (b) high lexical density, (c) rule count
# in target range. Reference-free.
# ---------------------------------------------------------------------------


_LEN_LO, _LEN_HI = 140, 320
_RULES_LO, _RULES_HI = 4, 7


def _density(text: str) -> float:
    """Approximate lexical density: unique words / total words, capped at 1."""
    words = [w.lower().strip(".·") for w in text.split() if w.strip(".·")]
    if not words:
        return 0.0
    uniq = len(set(words))
    return min(1.0, uniq / max(1, len(words)))


def _length_score(text: str) -> float:
    n = len(text)
    if _LEN_LO <= n <= _LEN_HI:
        return 1.0
    if n < _LEN_LO:
        return max(0.0, 0.99 * n / _LEN_LO)
    over = n - _LEN_HI
    return max(0.0, 1.0 - over / 200)


def _rule_count_score(rules: list[str]) -> float:
    n = len(rules)
    if _RULES_LO <= n <= _RULES_HI:
        return 1.0
    if n < _RULES_LO:
        return max(0.0, n / _RULES_LO)
    over = n - _RULES_HI
    return max(0.0, 1.0 - over / 4)


class _CompositeMetric(MetricBase):
    """Reference-free: length-band × lexical-density × rule-count-in-band.

    Rule count is recovered from the answer text itself — the offline
    leaf separates rules with ' · ', so counting that delimiter gives the
    same number both in training (BoN inner loop) and at final eval.
    """

    name = "composite"

    async def score(
        self, predicted: BaseModel, expected: BaseModel
    ) -> float:
        _ = expected
        text = str(getattr(predicted, "text", ""))
        # Approximate rule count: each rule is a ' · '-delimited segment
        # after the leading "<role>. " prefix, plus the original rule.
        # Counting separators gives `n_rules - 1`, so add one back.
        n_rules = (text.count(" · ") + 1) if text.strip() else 0
        length = _length_score(text)
        density = _density(text)
        rules_s = _rule_count_score(["x"] * n_rules)
        return (length + density + rules_s) / 3


class _ExpectedShape(BaseModel):
    """Reference-free expected_output placeholder (kept for typing parity)."""

    text: str = ""


# ---------------------------------------------------------------------------
# Mini in-process BestOfN: N stochastic forwards × judge by score.
#
# We deliberately reimplement a tight inner Best-of-N here rather than
# delegating to `operad.algorithms.Beam` because the sampling needs to
# vary per attempt (n=1 still needs `n` clones with different RNG seeds
# baked into `config.sampling.seed`), which Beam supports but at the cost
# of spinning up extra agent clones per call. For the demo we want every
# inner attempt to be visible in the algorithm-event stream.
# ---------------------------------------------------------------------------


class _BestOfNInner:
    """N stochastic forwards on the same agent; pick the highest-scoring.

    `n` parallel forwards are launched per row via `asyncio.gather`. In
    live mode the strands sampling layer drives the variance (different
    seeds per attempt); in this offline demo the leaf is deterministic,
    so all `n` attempts return the same answer and BoN collapses to the
    single-shot score — the pattern (parallel call fan-out) is what we
    demonstrate, not the lift from sampling.
    """

    def __init__(self, *, n: int, metric: MetricBase) -> None:
        if n < 1:
            raise ValueError("n must be >= 1")
        self.n = n
        self.metric = metric

    async def best_score(
        self, agent: Agent[Question, Answer], question: Question
    ) -> tuple[float, Answer]:
        # All N parallel — `agent.forward` is a pure function of declared
        # state, so concurrent calls on the same instance are safe.
        attempts = await asyncio.gather(*(agent(question) for _ in range(self.n)))
        scored = [
            (await self.metric.score(a.response, _ExpectedShape()), a.response)
            for a in attempts
        ]
        return max(scored, key=lambda p: p[0])


# ---------------------------------------------------------------------------
# Per-generation mutation strategies.
# ---------------------------------------------------------------------------


_RULE_BANK = [
    "Be concise.",
    "Cite concrete examples.",
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
    - gen 2: pruning (DropRule) + targeted grow
    - gen 3+: small mixed pool focused on tail of the rule list
    """
    pool: list[Op] = []
    if gen == 0:
        sample = rng.sample(_RULE_BANK, k=6)
        pool = [AppendRule(path="", rule=r) for r in sample]
    elif gen == 1:
        # ReplaceRule needs a valid index; sample replacements from bank.
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
        # Mixed pool, prefer the tail — refining what's already there.
        max_index = max(0, max(len(a.rules) for a in survivors) - 1)
        sample = rng.sample(_RULE_BANK, k=3)
        pool = [AppendRule(path="", rule=r) for r in sample]
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
        best_of_n: int = 3,
        top_k: int = 3,
        concurrency: int = 8,
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
        """Mean BestOfN score across the dataset, bounded by `sem`."""
        async with sem:
            scores: list[float] = []
            for question, _ in self._dataset:
                s, _ = await self._inner.best_score(agent, question)
                scores.append(s)
            return statistics.fmean(scores) if scores else 0.0

    async def step(self) -> None:  # type: ignore[override]
        """One generation: refresh mutations → mutate → BestOfN → top-K."""
        # First-step bootstrap: seed the population from the root.
        if self._population is None:
            seed_score = await self._evaluate_individual(
                self._root, asyncio.Semaphore(self._concurrency)
            )
            self._last_scores = [seed_score]
            # Use the first mutation set to fill the initial population.
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

        # Refresh mutation pool from the current population every generation.
        self._mutations = _mutations_for_generation(
            self._generation, self._population, self._rng
        )

        sem = asyncio.Semaphore(self._concurrency)
        scores = list(
            await asyncio.gather(
                *(self._evaluate_individual(a, sem) for a in self._population)
            )
        )
        ranked = sorted(
            range(self._population_size),
            key=lambda i: -scores[i],
        )
        survivor_indices = ranked[: self._top_k]
        survivors = [self._population[i] for i in survivor_indices]

        await self._emit_extended_event(
            scores=scores,
            survivor_indices=survivor_indices,
            mutation_family=self._family_label(),
        )

        # Refill: each survivor spawns (population_size - top_k) / top_k children
        # by re-mutating; tail rounded up so we always fill exactly N slots.
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
        ops = self._mutations
        kinds = sorted({op.name for op in ops})
        return ", ".join(kinds)

    async def _emit_extended_event(
        self,
        *,
        scores: list[float],
        survivor_indices: list[int],
        mutation_family: str,
    ) -> None:
        """Same shape as base `_emit_generation_event` plus our custom fields."""
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
                "ops": event.payload.get("op_attempt_counts", {}),
                "successes": event.payload.get("op_success_counts", {}),
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
    table = Table(title="Per-generation training (mutation × Best-of-N)", border_style="cyan")
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


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


_OFFLINE_CFG = Configuration(
    backend="llamacpp",
    host="127.0.0.1:0",
    model="offline-stub",
    sampling=Sampling(temperature=0.0, max_tokens=512),
)


async def main(args: argparse.Namespace) -> None:
    _rule("Stage 1 — assemble seed agent + dataset + metric")
    seed = _RoleRulesLeaf(config=_OFFLINE_CFG.model_copy(deep=True))
    seed.role = "You answer questions"
    seed.rules = ["Be helpful."]
    await seed.abuild()

    dataset = [
        (Question(text=q), _ExpectedShape())
        for q in (
            "Why are bees important?",
            "What is climate change?",
            "Define photosynthesis.",
            "How do vaccines work?",
            "What causes ocean tides?",
        )
    ]
    metric = _CompositeMetric()

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
            f"target length band: [{_LEN_LO}, {_LEN_HI}] chars\n"
            f"target rule count:  [{_RULES_LO}, {_RULES_HI}]\n"
            f"seed score:         {seed_score:.3f}\n"
            f"seed hash:          {seed_hash}\n"
            f"seed answer (len {len(seed_text)}):\n  {seed_text}"
        ),
    )

    _rule("Stage 2 — wire EvoGradientBestOfN")
    optimizer = EvoGradientBestOfN(
        list(seed.parameters()),
        # `_mutations` is replaced every step; the seed pool is overwritten.
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
                "evolving",
                total=args.generations,
                gen=0,
                best=0.0,
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
            print(f"  gen {gen_index + 1}/{args.generations}  best={last.get('best', 0.0):.3f}")
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
            f"wall time:     {elapsed:.2f}s for {args.generations} generations × "
            f"{args.population} × Best-of-{args.best_of_n}\n\n"
            f"final role:    {seed.role!r}\n"
            f"final rules:   {seed.rules}\n"
            f"final answer (len {len(final_text)}):\n  {final_text}"
        ),
    )

    assert final_score + 1e-9 >= seed_score, (
        f"score regressed: seed={seed_score} final={final_score}"
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--generations", type=int, default=4)
    p.add_argument("--population", type=int, default=8)
    p.add_argument("--top-k", dest="top_k", type=int, default=3)
    p.add_argument("--best-of-n", dest="best_of_n", type=int, default=3)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument(
        "--offline",
        action="store_true",
        help="Parity flag for verify.sh; the demo always runs offline.",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
