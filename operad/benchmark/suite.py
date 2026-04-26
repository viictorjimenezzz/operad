"""Small benchmark-suite runner built on the public benchmark primitives."""

from __future__ import annotations

import itertools
import math
import random
import statistics
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from ..core.agent import Agent
from ..data import random_split
from ..metrics.base import Metric
from ..runtime.observers.base import registry
from ..utils.ops import AppendRule, EditTask, SetTemperature
from ..utils.paths import set_path
from .dataset import Dataset
from .entry import Entry
from .evaluate import evaluate


AgentFactory = Callable[[bool], Agent[Any, Any]]
SweepGridFactory = Callable[[], dict[str, list[Any]]]


class BenchmarkTokens(BaseModel):
    prompt: int = 0
    completion: int = 0


class BenchmarkCell(BaseModel):
    task: str
    method: str
    seed: int
    metric: str
    score: float
    tokens: BenchmarkTokens = Field(default_factory=BenchmarkTokens)
    latency_s: float


class BenchmarkSummaryRow(BaseModel):
    task: str
    method: str
    mean: float
    std: float
    tokens_mean: int
    latency_mean: float
    n: int


class BenchmarkReport(BaseModel):
    cells: list[BenchmarkCell] = Field(default_factory=list)
    summary: list[BenchmarkSummaryRow] = Field(default_factory=list)
    headline_findings: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkRunConfig(BaseModel):
    tasks: list[str] | None = None
    methods: list[str] | None = None
    seeds: list[int] = Field(default_factory=lambda: [0, 1, 2])
    offline: bool = False
    max_examples: int | None = None
    train_epochs: int = 2
    split_fractions: tuple[float, float] = (0.8, 0.2)
    concurrency: int = 4
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkTask:
    key: str
    name: str
    dataset: Dataset[Any, Any]
    metrics: list[Metric]
    make_seed_agent: AgentFactory
    make_hand_edit_agent: AgentFactory | None = None
    make_sweep_grid: SweepGridFactory | None = None
    loss: Any = None

    @property
    def primary_metric(self) -> Metric:
        if not self.metrics:
            raise ValueError(f"benchmark task {self.key!r} has no metrics")
        return self.metrics[0]


@dataclass(frozen=True)
class BenchmarkContext:
    task: BenchmarkTask
    train: Dataset[Any, Any]
    test: Dataset[Any, Any]
    seed: int
    offline: bool
    train_epochs: int
    concurrency: int


MethodRunner = Callable[[BenchmarkContext], Awaitable[float]]


@dataclass(frozen=True)
class BenchmarkMethod:
    name: str
    supports_offline: bool
    runner: MethodRunner


class _TokenObserver:
    def __init__(self) -> None:
        self.prompt = 0
        self.completion = 0

    async def on_event(self, event: Any) -> None:
        if getattr(event, "kind", None) != "end":
            return
        out = getattr(event, "output", None)
        if out is None:
            return
        self.prompt += _int_or_zero(getattr(out, "prompt_tokens", None))
        self.completion += _int_or_zero(getattr(out, "completion_tokens", None))

    def totals(self) -> BenchmarkTokens:
        return BenchmarkTokens(prompt=self.prompt, completion=self.completion)


class BenchmarkSuite:
    """Run benchmark tasks across methods and seeds."""

    def __init__(
        self,
        tasks: list[BenchmarkTask],
        methods: list[BenchmarkMethod] | None = None,
    ) -> None:
        if not tasks:
            raise ValueError("BenchmarkSuite requires at least one task")
        self.tasks = _index_by_key(tasks, "task")
        self.methods = _index_by_key(
            methods if methods is not None else default_benchmark_methods(),
            "method",
        )

    async def run(self, config: BenchmarkRunConfig | None = None) -> BenchmarkReport:
        cfg = config or BenchmarkRunConfig()
        self.validate(cfg)
        tasks = self._resolve_tasks(cfg.tasks)
        methods = self._resolve_methods(cfg.methods, offline=cfg.offline)

        cells: list[BenchmarkCell] = []
        for task in tasks:
            dataset = _limit_dataset(task.dataset, cfg.max_examples)
            for method in methods:
                for seed in cfg.seeds:
                    train, test = random_split(
                        dataset,
                        list(cfg.split_fractions),
                        seed=seed,
                    )
                    ctx = BenchmarkContext(
                        task=task,
                        train=train,
                        test=test,
                        seed=seed,
                        offline=cfg.offline,
                        train_epochs=cfg.train_epochs,
                        concurrency=cfg.concurrency,
                    )
                    cells.append(await self._run_cell(ctx, method))

        summary = _summarize(cells)
        return BenchmarkReport(
            cells=cells,
            summary=summary,
            headline_findings=_headline_findings(summary),
            metadata=dict(cfg.metadata),
        )

    def validate(self, config: BenchmarkRunConfig) -> None:
        self._validate_config(config)
        self._resolve_tasks(config.tasks)
        self._resolve_methods(config.methods, offline=config.offline)

    def _resolve_tasks(self, selected: list[str] | None) -> list[BenchmarkTask]:
        keys = list(self.tasks) if selected is None else selected
        if not keys:
            raise ValueError("no benchmark tasks selected")
        unknown = sorted(k for k in keys if k not in self.tasks)
        if unknown:
            raise ValueError(f"unknown benchmark task(s): {', '.join(unknown)}")
        return [self.tasks[k] for k in keys]

    def _resolve_methods(
        self,
        selected: list[str] | None,
        *,
        offline: bool,
    ) -> list[BenchmarkMethod]:
        if selected is None:
            methods = list(self.methods.values())
            if offline:
                methods = [m for m in methods if m.supports_offline]
            if not methods:
                raise ValueError("no benchmark methods selected")
            return methods

        if not selected:
            raise ValueError("no benchmark methods selected")
        unknown = sorted(k for k in selected if k not in self.methods)
        if unknown:
            raise ValueError(f"unknown benchmark method(s): {', '.join(unknown)}")
        methods = [self.methods[k] for k in selected]
        blocked = [m.name for m in methods if offline and not m.supports_offline]
        if blocked:
            allowed = [m.name for m in self.methods.values() if m.supports_offline]
            raise ValueError(
                "offline mode cannot run method(s): "
                f"{', '.join(blocked)}; choose from {', '.join(allowed)}"
            )
        return methods

    def _validate_config(self, cfg: BenchmarkRunConfig) -> None:
        if not cfg.seeds:
            raise ValueError("BenchmarkRunConfig.seeds must not be empty")
        if cfg.max_examples is not None and cfg.max_examples < 1:
            raise ValueError("BenchmarkRunConfig.max_examples must be >= 1")
        if cfg.train_epochs < 1:
            raise ValueError("BenchmarkRunConfig.train_epochs must be >= 1")
        if cfg.concurrency < 1:
            raise ValueError("BenchmarkRunConfig.concurrency must be >= 1")
        if abs(sum(cfg.split_fractions) - 1.0) > 1e-6:
            raise ValueError("BenchmarkRunConfig.split_fractions must sum to 1.0")

    async def _run_cell(
        self,
        ctx: BenchmarkContext,
        method: BenchmarkMethod,
    ) -> BenchmarkCell:
        observer = _TokenObserver()
        started = time.perf_counter()
        registry.register(observer)
        try:
            score = await method.runner(ctx)
        finally:
            registry.unregister(observer)
        elapsed = time.perf_counter() - started
        if math.isnan(score):
            raise ValueError(
                f"benchmark cell produced NaN: {ctx.task.name}/{method.name}/"
                f"seed={ctx.seed}"
            )
        return BenchmarkCell(
            task=ctx.task.name,
            method=method.name,
            seed=ctx.seed,
            metric=ctx.task.primary_metric.name,
            score=score,
            tokens=observer.totals(),
            latency_s=elapsed,
        )


ALL_METHODS = ("no_train", "hand_edit", "sweep", "tgd", "momentum", "evo", "opro", "ape")
OFFLINE_METHODS = ("no_train", "hand_edit", "sweep", "evo")


def default_benchmark_methods() -> list[BenchmarkMethod]:
    return [
        BenchmarkMethod("no_train", True, _run_no_train),
        BenchmarkMethod("hand_edit", True, _run_hand_edit),
        BenchmarkMethod("sweep", True, _run_sweep),
        BenchmarkMethod("tgd", False, _run_auto_tune("textgrad")),
        BenchmarkMethod("momentum", False, _run_auto_tune("momentum")),
        BenchmarkMethod("evo", True, _run_auto_tune("evo")),
        BenchmarkMethod("opro", False, _run_auto_tune("opro")),
        BenchmarkMethod("ape", False, _run_auto_tune("ape")),
    ]


async def _run_no_train(ctx: BenchmarkContext) -> float:
    agent = ctx.task.make_seed_agent(ctx.offline)
    await agent.abuild()
    return await _evaluate_primary(agent, ctx)


async def _run_hand_edit(ctx: BenchmarkContext) -> float:
    if ctx.task.make_hand_edit_agent is None:
        raise ValueError(f"benchmark task {ctx.task.key!r} has no hand-edit agent")
    agent = ctx.task.make_hand_edit_agent(ctx.offline)
    await agent.abuild()
    return await _evaluate_primary(agent, ctx)


async def _run_sweep(ctx: BenchmarkContext) -> float:
    if ctx.task.make_sweep_grid is None:
        raise ValueError(f"benchmark task {ctx.task.key!r} has no sweep grid")

    seed = ctx.task.make_seed_agent(ctx.offline)
    await seed.abuild()
    grid = ctx.task.make_sweep_grid()
    keys = list(grid)
    combos = [
        dict(zip(keys, values))
        for values in itertools.product(*(grid[k] for k in keys))
    ] or [{}]

    best_score = float("-inf")
    best_agent = seed.clone()
    for combo in combos:
        candidate = seed.clone()
        for path, value in combo.items():
            set_path(candidate, path, value)
        await candidate.abuild()
        score = await _evaluate_primary(candidate, ctx, dataset=ctx.train)
        if score > best_score:
            best_score = score
            best_agent = candidate

    if not best_agent._built:
        await best_agent.abuild()
    return await _evaluate_primary(best_agent, ctx)


def _run_auto_tune(kind: str) -> MethodRunner:
    async def _runner(ctx: BenchmarkContext) -> float:
        agent = ctx.task.make_seed_agent(ctx.offline)
        await agent.abuild()
        agent.mark_trainable(task=True, rules=True)

        kwargs: dict[str, Any] = {}
        if kind == "evo":
            kwargs["rng"] = random.Random(ctx.seed)
            kwargs["mutations"] = _demo_mutations()

        tuned = await agent.auto_tune(
            list(ctx.train),
            ctx.task.primary_metric,
            kind=kind,  # type: ignore[arg-type]
            epochs=ctx.train_epochs,
            generations=ctx.train_epochs,
            population_size=4,
            loss=ctx.task.loss,
            **kwargs,
        )
        if not tuned._built:
            await tuned.abuild()
        return await _evaluate_primary(tuned, ctx)

    return _runner


def _demo_mutations() -> list[Any]:
    return [
        AppendRule(path="", rule="Be concise and precise."),
        AppendRule(path="", rule="Output only the required fields."),
        EditTask(path="", task="Be precise and output only the required field values."),
        SetTemperature(path="", temperature=0.0),
        SetTemperature(path="", temperature=0.3),
        SetTemperature(path="", temperature=0.7),
    ]


async def _evaluate_primary(
    agent: Agent[Any, Any],
    ctx: BenchmarkContext,
    *,
    dataset: Dataset[Any, Any] | None = None,
) -> float:
    report = await evaluate(
        agent,
        dataset or ctx.test,
        ctx.task.metrics,
        concurrency=ctx.concurrency,
    )
    return float(report.summary[ctx.task.primary_metric.name])


def _limit_dataset(
    dataset: Dataset[Any, Any],
    max_examples: int | None,
) -> Dataset[Any, Any]:
    if max_examples is None:
        return dataset
    entries: list[Entry[Any, Any]] = list(dataset)[: min(max_examples, len(dataset))]
    return Dataset(entries, name=dataset.name, version=dataset.version)


def _summarize(cells: list[BenchmarkCell]) -> list[BenchmarkSummaryRow]:
    groups: dict[tuple[str, str], list[BenchmarkCell]] = defaultdict(list)
    for cell in cells:
        groups[(cell.task, cell.method)].append(cell)

    rows: list[BenchmarkSummaryRow] = []
    for (task, method), group in sorted(groups.items()):
        scores = [c.score for c in group]
        tokens = [c.tokens.prompt + c.tokens.completion for c in group]
        latencies = [c.latency_s for c in group]
        rows.append(
            BenchmarkSummaryRow(
                task=task,
                method=method,
                mean=statistics.mean(scores),
                std=statistics.stdev(scores) if len(scores) > 1 else 0.0,
                tokens_mean=int(statistics.mean(tokens)),
                latency_mean=statistics.mean(latencies),
                n=len(group),
            )
        )
    return rows


def _headline_findings(summary: list[BenchmarkSummaryRow]) -> dict[str, str]:
    findings: dict[str, str] = {}
    for task in sorted({r.task for r in summary}):
        rows = sorted((r for r in summary if r.task == task), key=lambda r: -r.mean)
        if not rows:
            continue
        best = rows[0]
        baseline = next((r for r in rows if r.method == "no_train"), None)
        if baseline is None:
            findings[task] = f"Best method: {best.method} (mean={best.mean:.3f})."
            continue
        delta = best.mean - baseline.mean
        sign = "+" if delta >= 0 else ""
        findings[task] = (
            f"Best method: {best.method} (mean={best.mean:.3f}). "
            f"Delta vs no_train: {sign}{delta:.3f}. "
            f"Token cost for best: {best.tokens_mean}."
        )
    return findings


def _index_by_key(items: list[Any], noun: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        key = item.key if noun == "task" else item.name
        if key in out:
            raise ValueError(f"duplicate benchmark {noun}: {key!r}")
        out[key] = item
    return out


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "ALL_METHODS",
    "OFFLINE_METHODS",
    "BenchmarkCell",
    "BenchmarkContext",
    "BenchmarkMethod",
    "BenchmarkReport",
    "BenchmarkRunConfig",
    "BenchmarkSuite",
    "BenchmarkSummaryRow",
    "BenchmarkTask",
    "BenchmarkTokens",
    "default_benchmark_methods",
]
