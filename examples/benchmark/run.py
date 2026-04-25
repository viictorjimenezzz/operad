"""Benchmark: TextGrad vs Sweep vs no-training across three tasks.

Compares operad's optimizers (TGD, Momentum, EvoGradient, OPRO, APE),
a Sweep baseline, a hand-edited prompt baseline, and a frozen seed.

Usage:
    # Offline smoke (no LLM)
    uv run python examples/benchmark/run.py --offline --max-examples 5 --seeds 0

    # Full run (live LLM, slow)
    uv run python examples/benchmark/run.py --out report.json

    # Subset
    uv run python examples/benchmark/run.py --tasks cls,sum --methods no_train,tgd
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from operad import evaluate
from operad.benchmark.dataset import Dataset
from operad.data import random_split
from operad.utils.ops import (
    AppendRule,
    EditTask,
    SetTemperature,
)

from . import task_classification as _cls
from . import task_summarization as _sum
from . import task_tool_use as _tool
from ._shared import LatencyTimer, TokenCounter

# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------

_TASK_MAP = {
    "cls": ("classification", _cls),
    "sum": ("summarization", _sum),
    "tool": ("tool_use", _tool),
}

ALL_TASKS = list(_TASK_MAP)
ALL_METHODS = ["no_train", "hand_edit", "sweep", "tgd", "momentum", "evo", "opro", "ape"]

# ---------------------------------------------------------------------------
# Sweep helpers
# ---------------------------------------------------------------------------


def _make_sweep_cls(task_module: Any, agent_seed: Any) -> type:
    grid = task_module.make_sweep_grid()

    class _BenchSweep(Sweep):
        seed = agent_seed

    return _BenchSweep(grid)


async def _run_sweep(
    task_module: Any,
    train_ds: Dataset,
    test_ds: Dataset,
    offline: bool,
) -> tuple[float, float]:
    """Grid-search best combo on train; evaluate on test.

    Returns (train_best_score, test_score).
    """
    seed = task_module.make_seed_agent(offline=offline)
    await seed.abuild()
    grid = task_module.make_sweep_grid()
    if offline:
        grid = {k: v[:1] for k, v in grid.items()}

    import itertools
    from operad.utils.paths import set_path

    keys = list(grid)
    combos = [dict(zip(keys, vals)) for vals in itertools.product(*[grid[k] for k in keys])]
    best_score = -1.0
    best_agent = seed.clone()

    for combo in combos:
        candidate = seed.clone()
        for dotted, value in combo.items():
            set_path(candidate, dotted, value)
        await candidate.abuild()
        report = await evaluate(candidate, train_ds, task_module.METRICS)
        score = float(report.summary.get(task_module.METRICS[0].name, 0.0))
        if score > best_score:
            best_score = score
            best_agent = candidate

    if not best_agent._built:
        await best_agent.abuild()

    test_report = await evaluate(best_agent, test_ds, task_module.METRICS)
    test_score = float(test_report.summary.get(task_module.METRICS[0].name, 0.0))
    return best_score, test_score


# ---------------------------------------------------------------------------
# Per-method runners
# ---------------------------------------------------------------------------

async def _run_no_train(
    task_module: Any,
    test_ds: Dataset,
    offline: bool,
    token_counter: TokenCounter,
) -> float:
    agent = task_module.make_seed_agent(offline=offline)
    await agent.abuild()
    handle = token_counter.attach(agent)
    report = await evaluate(agent, test_ds, task_module.METRICS)
    handle.remove()
    return float(report.summary.get(task_module.METRICS[0].name, 0.0))


async def _run_hand_edit(
    task_module: Any,
    test_ds: Dataset,
    offline: bool,
    token_counter: TokenCounter,
) -> float:
    agent = task_module.make_hand_edit_agent(offline=offline)
    await agent.abuild()
    handle = token_counter.attach(agent)
    report = await evaluate(agent, test_ds, task_module.METRICS)
    handle.remove()
    return float(report.summary.get(task_module.METRICS[0].name, 0.0))


async def _run_sweep_method(
    task_module: Any,
    train_ds: Dataset,
    test_ds: Dataset,
    offline: bool,
    timer: LatencyTimer,
    token_counter: TokenCounter,
) -> float:
    with timer:
        _, test_score = await _run_sweep(task_module, train_ds, test_ds, offline)
    return test_score


async def _run_auto_tune(
    task_module: Any,
    train_ds: Dataset,
    test_ds: Dataset,
    offline: bool,
    kind: str,
    epochs: int,
    timer: LatencyTimer,
    token_counter: TokenCounter,
) -> float:
    agent = task_module.make_seed_agent(offline=offline)
    await agent.abuild()
    agent.mark_trainable(task=True, rules=True)

    mutations = None
    if kind == "evo":
        mutations = [
            AppendRule(path="", rule="Be concise and precise."),
            AppendRule(path="", rule="Output only the required fields."),
            EditTask(path="", task="Be precise and output only the required field values."),
            SetTemperature(path="", temperature=0.0),
            SetTemperature(path="", temperature=0.3),
            SetTemperature(path="", temperature=0.7),
        ]

    dataset_list = list(train_ds)

    with timer:
        handle = token_counter.attach(agent)
        try:
            tuned = await agent.auto_tune(
                dataset_list,
                task_module.METRICS[0],
                kind=kind,
                epochs=epochs,
                mutations=mutations,
                population_size=4,
                generations=epochs,
                loss=task_module.LOSS_FN,
            )
        finally:
            handle.remove()

    if not tuned._built:
        await tuned.abuild()

    report = await evaluate(tuned, test_ds, task_module.METRICS)
    return float(report.summary.get(task_module.METRICS[0].name, 0.0))


# ---------------------------------------------------------------------------
# Main cell runner
# ---------------------------------------------------------------------------

async def run_cell(
    task_key: str,
    method: str,
    seed_val: int,
    *,
    offline: bool,
    max_examples: int | None,
    train_epochs: int,
) -> dict[str, Any]:
    task_name, task_module = _TASK_MAP[task_key]
    dataset = task_module.DATASET

    if max_examples is not None:
        n = min(max_examples, len(dataset))
        entries = list(dataset)[:n]
        from operad.benchmark import Dataset as _DS
        dataset = _DS(entries, name=dataset.name, version=dataset.version)

    splits = random_split(dataset, [0.6, 0.2, 0.2], seed=seed_val)
    train_ds, val_ds, test_ds = splits[0], splits[1], splits[2]

    timer = LatencyTimer()
    counter = TokenCounter()

    score: float = 0.0

    try:
        if method == "no_train":
            with timer:
                score = await _run_no_train(task_module, test_ds, offline, counter)

        elif method == "hand_edit":
            with timer:
                score = await _run_hand_edit(task_module, test_ds, offline, counter)

        elif method == "sweep":
            score = await _run_sweep_method(
                task_module, train_ds, test_ds, offline, timer, counter
            )

        elif method in {"tgd", "momentum", "evo", "opro", "ape"}:
            kind_map = {
                "tgd": "textgrad",
                "momentum": "momentum",
                "evo": "evo",
                "opro": "opro",
                "ape": "ape",
            }
            score = await _run_auto_tune(
                task_module,
                train_ds,
                test_ds,
                offline,
                kind=kind_map[method],
                epochs=train_epochs,
                timer=timer,
                token_counter=counter,
            )

        else:
            raise ValueError(f"Unknown method: {method!r}")

    except Exception as exc:
        print(f"  [ERROR] {task_name}/{method}/seed={seed_val}: {exc}", file=sys.stderr)
        score = float("nan")

    return {
        "task": task_name,
        "method": method,
        "seed": seed_val,
        "metric": task_module.METRICS[0].name,
        "score": score,
        "tokens": counter.totals(),
        "latency_s": timer.elapsed,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _summarize(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from collections import defaultdict

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cells:
        if c["score"] == c["score"]:  # not NaN
            groups[(c["task"], c["method"])].append(c)

    rows = []
    for (task, method), group in sorted(groups.items()):
        scores = [g["score"] for g in group]
        tokens = [g["tokens"]["prompt"] + g["tokens"]["completion"] for g in group]
        latencies = [g["latency_s"] for g in group]
        rows.append({
            "task": task,
            "method": method,
            "mean": statistics.mean(scores),
            "std": statistics.stdev(scores) if len(scores) > 1 else 0.0,
            "tokens_mean": int(statistics.mean(tokens)),
            "latency_mean": statistics.mean(latencies),
            "n": len(scores),
        })
    return rows


def _headline_findings(summary: list[dict[str, Any]]) -> dict[str, str]:
    findings: dict[str, str] = {}
    tasks = sorted({r["task"] for r in summary})
    for task in tasks:
        rows = sorted(
            [r for r in summary if r["task"] == task],
            key=lambda r: -r["mean"],
        )
        if not rows:
            continue
        best = rows[0]
        baseline = next((r for r in rows if r["method"] == "no_train"), None)
        if baseline:
            delta = best["mean"] - baseline["mean"]
            sign = "+" if delta >= 0 else ""
            findings[task] = (
                f"Best method: {best['method']} (mean={best['mean']:.3f}). "
                f"Delta vs no_train: {sign}{delta:.3f}. "
                f"Token cost for best: {best['tokens_mean']}."
            )
        else:
            findings[task] = f"Best method: {best['method']} (mean={best['mean']:.3f})."
    return findings


def _print_markdown(summary: list[dict[str, Any]], findings: dict[str, str]) -> None:
    header = "| task | method | metric | mean | std | tokens | latency |"
    sep    = "|------|--------|--------|------|-----|--------|---------|"
    print(header)
    print(sep)
    for r in summary:
        # retrieve metric name from task_map
        task_key = next(k for k, (n, _) in _TASK_MAP.items() if n == r["task"])
        metric_name = _TASK_MAP[task_key][1].METRICS[0].name
        print(
            f"| {r['task']} | {r['method']} | {metric_name} "
            f"| {r['mean']:.3f} | {r['std']:.3f} "
            f"| {r['tokens_mean']} | {r['latency_mean']:.1f}s |"
        )

    print("\n## Headline Findings\n")
    for task, finding in findings.items():
        print(f"**{task}**: {finding}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--offline", action="store_true", help="Use offline stubs (no LLM).")
    p.add_argument(
        "--tasks",
        default=",".join(ALL_TASKS),
        help="Comma-separated task keys: cls,sum,tool",
    )
    p.add_argument(
        "--methods",
        default=",".join(ALL_METHODS),
        help="Comma-separated methods.",
    )
    p.add_argument(
        "--seeds",
        default="0,1,2",
        help="Comma-separated random seeds.",
    )
    p.add_argument(
        "--train-epochs",
        type=int,
        default=2,
        help="Training epochs / generations for gradient-based methods.",
    )
    p.add_argument(
        "--max-examples",
        type=int,
        default=None,
        help="Cap dataset at N examples per split (useful for --offline smoke).",
    )
    p.add_argument(
        "--out",
        default="report.json",
        help="Output path for report.json.",
    )
    return p.parse_args()


async def main(args: argparse.Namespace) -> None:
    tasks = [t.strip() for t in args.tasks.split(",") if t.strip() in _TASK_MAP]
    methods = [m.strip() for m in args.methods.split(",") if m.strip() in ALL_METHODS]
    seeds = [int(s.strip()) for s in args.seeds.split(",")]

    if not tasks:
        print("No valid tasks specified.", file=sys.stderr)
        sys.exit(1)
    if not methods:
        print("No valid methods specified.", file=sys.stderr)
        sys.exit(1)

    total_cells = len(tasks) * len(methods) * len(seeds)
    print(f"Running {total_cells} cells: {tasks} × {methods} × seeds={seeds}")
    if args.offline:
        print("  Mode: OFFLINE (no LLM calls)")
    print()

    cells: list[dict[str, Any]] = []
    done = 0

    for task_key in tasks:
        task_name = _TASK_MAP[task_key][0]
        for method in methods:
            for seed_val in seeds:
                done += 1
                print(f"[{done}/{total_cells}] {task_name}/{method}/seed={seed_val} ...", end=" ", flush=True)
                t0 = time.perf_counter()
                cell = await run_cell(
                    task_key,
                    method,
                    seed_val,
                    offline=args.offline,
                    max_examples=args.max_examples,
                    train_epochs=args.train_epochs,
                )
                elapsed = time.perf_counter() - t0
                score_str = f"{cell['score']:.3f}" if cell["score"] == cell["score"] else "ERROR"
                print(f"score={score_str}  ({elapsed:.1f}s)")
                cells.append(cell)

    summary = _summarize(cells)
    findings = _headline_findings(summary)

    report = {
        "cells": cells,
        "summary": summary,
        "headline_findings": findings,
    }

    if args.out and args.out != "/dev/null":
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to {out_path}")

    print("\n" + "=" * 72)
    _print_markdown(summary, findings)


if __name__ == "__main__":
    asyncio.run(main(_parse_args()))
