"""Example 6 - dashboard training and optimizer coverage.

This script runs compact live Trainer sessions for the optimizer families
that are not already covered by examples/03..04:

* TextualGradientDescent
* MomentumTextGrad
* APEOptimizer

Run modes:

    uv run python examples/06_training_dashboard.py
    uv run python examples/06_training_dashboard.py --optimizer textgrad
    uv run python examples/06_training_dashboard.py --dashboard --no-open
    uv run python examples/06_training_dashboard.py --offline
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from operad import Configuration, evaluate
from operad.agents import Reasoner
from operad.benchmark import Dataset
from operad.core.config import Resilience, Sampling
from operad.data import DataLoader
from operad.metrics.metric import Metric
from operad.optim.backprop.tape import tape
from operad.optim.backprop.traceback import PromptTraceback
from operad.optim.losses import MetricLoss
from operad.optim.optimizers.ape import APEOptimizer
from operad.optim.optimizers.momentum import MomentumTextGrad
from operad.optim.optimizers.tgd import TextualGradientDescent
from operad.optim.parameter import Parameter, TextualGradient
from operad.optim.schedulers.lr import StepLR
from operad.runtime import set_limit
from operad.runtime.events import AlgorithmEvent
from operad.runtime.observers.base import Event, registry
from operad.train import PromptDrift, Trainer

from _config import local_config, server_reachable
from utils import (
    LengthBandMetric,
    attach_dashboard,
    parse_dashboard_target,
    print_dataset_table,
    print_panel,
    print_rule,
)


_SCRIPT = "06_training_dashboard"
DEFAULT_DASHBOARD = "127.0.0.1:7860"
_LOCAL_BACKENDS = {"llamacpp", "lmstudio", "ollama"}
_OPTIMIZERS = ("textgrad", "momentum", "ape")
_TARGET_LO, _TARGET_HI = 180, 320
_TRACEBACK_DIR = Path(".context/example_tracebacks")


class Question(BaseModel):
    text: str = Field(default="", description="A short dashboard QA question.")


class Answer(BaseModel):
    text: str = Field(default="", description="The answer body.")


class _RunIdCollector:
    """Collect algorithm run ids for a final dashboard index."""

    def __init__(self) -> None:
        self.run_ids: dict[str, list[str]] = defaultdict(list)

    async def on_event(self, event: Event) -> None:
        if not isinstance(event, AlgorithmEvent):
            return
        if event.kind != "algo_start":
            return
        runs = self.run_ids[event.algorithm_path]
        if event.run_id and event.run_id not in runs:
            runs.append(event.run_id)

    def body(self) -> str:
        if not self.run_ids:
            return "(no algorithm runs captured)"
        lines: list[str] = []
        for name in sorted(self.run_ids):
            ids = ", ".join(self.run_ids[name])
            lines.append(f"{name}: {ids}")
        return "\n".join(lines)


class DashboardTrainer(Trainer[Question, Answer]):
    """Trainer variant that keeps this example focused on optimizer rewrites.

    The library's default Trainer backprop path uses helper agents that
    need their own provider config. For this example, MetricLoss already
    yields a useful text critique, so we assign that critique directly to
    each trainable parameter. The optimizer step still goes through the
    real live optimizer agents.
    """

    async def _run_batch(self, batch: Any) -> tuple[float, int]:
        params = _flatten_optimizer_params(self.optimizer)
        loss_sum = 0.0
        sample_count = 0
        tape_entries_total = 0

        for idx, x, y in zip(batch.indices, batch.inputs, batch.expected):
            async with tape() as t:
                output = await self.agent(x)
            tape_entries_total += len(t.entries)
            score, grad = await self.loss_fn.compute(output.response, y)
            loss_sum += score
            sample_count += 1
            self.last_epoch_per_sample_severity[idx] = grad.severity

            if grad.severity <= 0:
                continue
            if self.traceback_dir is not None:
                self._last_prompt_traceback = PromptTraceback.from_run(t, grad)
            for p in params:
                if not p.requires_grad:
                    continue
                p.grad = TextualGradient(
                    message=grad.message,
                    by_field={p.path: grad.message},
                    severity=grad.severity,
                    target_paths=[p.path],
                )

        self._last_batch_tape_entries = tape_entries_total
        mean_loss = loss_sum / sample_count if sample_count else 0.0
        return mean_loss, sample_count


def _flatten_optimizer_params(optimizer: Any) -> list[Parameter[Any]]:
    params: list[Parameter[Any]] = []
    for group in optimizer.param_groups:
        params.extend(group.params)
    return params


def _cfg_for(
    cfg: Configuration,
    *,
    temperature: float,
    max_tokens: int = 1024,
) -> Configuration:
    return cfg.model_copy(
        deep=True,
        update={"sampling": Sampling(temperature=temperature, max_tokens=max_tokens)},
    )


def _one_line(value: Any, limit: int = 110) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _make_dataset() -> Dataset[Question, Answer]:
    return Dataset(
        [
            (Question(text="What should I inspect after a Beam run?"), Answer()),
            (Question(text="How can I tell whether Trainer drift was captured?"), Answer()),
        ],
        name="dashboard-training-example",
        version="v1",
    )


def _make_metric() -> LengthBandMetric:
    return LengthBandMetric(lo=_TARGET_LO, hi=_TARGET_HI, over_decay=600)


def _make_loss(metric: Metric) -> MetricLoss:
    def _gradient(predicted: BaseModel, expected: BaseModel | None, score: float) -> str:
        _ = expected
        text = str(getattr(predicted, "text", ""))
        return (
            f"length_band score={score:.3f}; answer length={len(text)} chars. "
            f"Rewrite the task/rules so answers land in {_TARGET_LO}-{_TARGET_HI} "
            "characters, use two concrete sentences, and mention the relevant dashboard tab."
        )

    return MetricLoss(
        metric,
        gradient_formatter=_gradient,
        severity_fn=lambda score: max(0.25, 1.0 - score),
        null_threshold=1.01,
    )


async def _make_seed(cfg: Configuration) -> Reasoner:
    seed = Reasoner(
        config=_cfg_for(cfg, temperature=0.0),
        input=Question,
        output=Answer,
        role="You answer dashboard QA questions for operad maintainers.",
        task="Write a useful answer.",
        rules=(
            "Mention the relevant dashboard rail or tab when possible.",
            "Avoid long background explanations.",
        ),
    )
    seed.mark_trainable(task=True, rules=True)
    await seed.abuild()
    return seed


def _param_snapshot(agent: Reasoner) -> dict[str, str]:
    return {
        path: repr(param.read())
        for path, param in agent.named_parameters()
        if param.requires_grad
    }


def _changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(path for path, value in after.items() if before.get(path) != value)


async def _ape_evaluator_factory(
    seed: Reasoner,
    dataset: Dataset[Question, Answer],
    metric: Metric,
) -> Any:
    lock = asyncio.Lock()

    async def _evaluate(param: Parameter[Any], candidate: Any) -> float:
        async with lock:
            old = param.read()
            param.write(candidate)
            try:
                await seed.abuild()
                report = await evaluate(seed, dataset, [metric])
                return float(report.summary[metric.name])
            finally:
                param.write(old)
                await seed.abuild()

    return _evaluate


async def _run_optimizer(
    *,
    name: str,
    cfg: Configuration,
    optimizer_cfg: Configuration,
    dataset: Dataset[Question, Answer],
    metric: Metric,
    epochs: int,
) -> None:
    print_rule(f"Trainer - {name}")
    seed = await _make_seed(cfg)
    before_params = _param_snapshot(seed)
    seed_hash = seed.hash_content
    seed_report = await evaluate(seed, dataset, [metric])
    seed_score = float(seed_report.summary[metric.name])

    params = list(seed.parameters())
    if name == "textgrad":
        optimizer = TextualGradientDescent(params, lr=0.7, config=optimizer_cfg)
    elif name == "momentum":
        optimizer = MomentumTextGrad(
            params,
            lr=0.7,
            config=optimizer_cfg,
            history_k=2,
        )
    elif name == "ape":
        optimizer = APEOptimizer(
            params,
            lr=1.0,
            config=optimizer_cfg,
            evaluator=await _ape_evaluator_factory(seed, dataset, metric),
            k=2,
        )
    else:
        raise ValueError(f"unknown optimizer {name!r}")

    scheduler = StepLR(optimizer, step_size=1, gamma=0.5)
    trainer = DashboardTrainer(
        seed,
        optimizer,
        _make_loss(metric),
        scheduler=scheduler,
        callbacks=[PromptDrift(emit_every=1)],
        metrics=[metric],
        traceback_dir=_TRACEBACK_DIR,
    )
    loader = DataLoader(dataset, batch_size=1, shuffle=False)

    print_panel(
        "Setup",
        (
            f"optimizer:    {type(optimizer).__name__}\n"
            f"epochs:       {epochs}\n"
            f"seed score:   {seed_score:.3f}\n"
            f"seed hash:    {seed_hash}\n"
            f"trainable:    {', '.join(before_params)}"
        ),
    )

    report = await trainer.fit(loader, val_ds=dataset, epochs=epochs)
    final_report = await trainer.evaluate(dataset)
    final_score = float(final_report.summary[metric.name])
    after_params = _param_snapshot(seed)
    changed = _changed_paths(before_params, after_params)
    final_hash = seed.hash_content
    sample = (await trainer.predict(Question(text="What should I inspect after a Beam run?"))).response.text

    print_panel(
        "Result",
        (
            f"optimizer:      {type(optimizer).__name__}\n"
            f"best epoch:     {report.best_epoch}\n"
            f"score:          {seed_score:.3f} -> {final_score:.3f}\n"
            f"hash:           {seed_hash} -> {final_hash}\n"
            f"changed paths:  {', '.join(changed) if changed else '(none)'}\n"
            f"tracebacks:     {_TRACEBACK_DIR}\n"
            f"sample answer:  {_one_line(sample, 180)}"
        ),
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
    if cfg.backend in _LOCAL_BACKENDS and not server_reachable(cfg.host or ""):
        print(
            f"[{_SCRIPT}] cannot reach {cfg.host} - start llama-server",
            file=sys.stderr,
        )
        raise SystemExit(1)
    set_limit(backend=cfg.backend, host=cfg.host, concurrency=2)

    selected = list(_OPTIMIZERS if args.optimizer == "all" else (args.optimizer,))
    dataset = _make_dataset()
    metric = _make_metric()
    optimizer_cfg = _cfg_for(cfg, temperature=0.7, max_tokens=1024)

    print_dataset_table(
        [(entry.input, entry.expected_output or Answer()) for entry in dataset],
        title="Training dataset",
    )
    print_panel(
        "Metric",
        (
            f"name:         {metric.name}\n"
            f"target band:  len(answer.text) in [{_TARGET_LO}, {_TARGET_HI}] chars\n"
            "gradient:     direct MetricLoss critique assigned to task/rules"
        ),
    )

    collector = _RunIdCollector()
    registry.register(collector)
    try:
        for name in selected:
            await _run_optimizer(
                name=name,
                cfg=cfg,
                optimizer_cfg=optimizer_cfg,
                dataset=dataset,
                metric=metric,
                epochs=args.epochs,
            )
    finally:
        registry.unregister(collector)

    print_rule("Dashboard run ids")
    print_panel("Training runs", collector.body())
    if attached:
        host, port = parse_dashboard_target(args.dashboard, default=DEFAULT_DASHBOARD)
        print(
            f"[dashboard] still live at http://{host}:{port}  "
            "(ctrl+c the dashboard server to stop)"
        )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--optimizer",
        choices=(*_OPTIMIZERS, "all"),
        default="all",
        help="Run one optimizer family or all remaining dashboard-training families.",
    )
    p.add_argument("--epochs", type=int, default=2)
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
