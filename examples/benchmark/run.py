"""Run the operad benchmark example.

Usage:
    # Offline smoke, no model provider required.
    uv run python -m examples.benchmark.run --offline --max-examples 5 --seeds 0

    # Full live run.
    uv run python -m examples.benchmark.run --out report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from operad.benchmark import (
    ALL_METHODS,
    OFFLINE_METHODS,
    BenchmarkReport,
    BenchmarkRunConfig,
    BenchmarkSuite,
)

from .task_classification import TASK as CLASSIFICATION_TASK
from .task_summarization import TASK as SUMMARIZATION_TASK
from .task_tool_use import TASK as TOOL_USE_TASK


TASKS = [CLASSIFICATION_TASK, SUMMARIZATION_TASK, TOOL_USE_TASK]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--offline", action="store_true", help="Use offline stubs.")
    p.add_argument(
        "--tasks",
        default=None,
        help="Comma-separated task keys. Default: cls,sum,tool.",
    )
    p.add_argument(
        "--methods",
        default=None,
        help=(
            "Comma-separated method names. Offline default: "
            f"{','.join(OFFLINE_METHODS)}. Live default: {','.join(ALL_METHODS)}."
        ),
    )
    p.add_argument("--seeds", default="0,1,2", help="Comma-separated random seeds.")
    p.add_argument(
        "--train-epochs",
        type=int,
        default=2,
        help="Training epochs / generations for optimization methods.",
    )
    p.add_argument(
        "--max-examples",
        type=int,
        default=None,
        help="Cap total rows per task before splitting.",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Per-evaluation concurrency passed to operad.benchmark.evaluate.",
    )
    p.add_argument("--out", default="report.json", help="Output JSON path.")
    p.add_argument(
        "--dashboard",
        default=None,
        help="Optional dashboard base URL to POST report to /benchmarks/_ingest.",
    )
    return p.parse_args()


async def main(args: argparse.Namespace) -> BenchmarkReport:
    config = BenchmarkRunConfig(
        tasks=_csv(args.tasks),
        methods=_csv(args.methods),
        seeds=[int(s) for s in _csv(args.seeds) or []],
        offline=args.offline,
        max_examples=args.max_examples,
        train_epochs=args.train_epochs,
        concurrency=args.concurrency,
        metadata={"name": "operad benchmark example"},
    )

    suite = BenchmarkSuite(TASKS)
    suite.validate(config)
    _print_run_header(config)
    report = await suite.run(config)

    payload = report.model_dump(mode="json")
    if args.out and args.out != "/dev/null":
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nReport written to {out_path}")

    if args.dashboard:
        try:
            _post_to_dashboard(args.dashboard, payload)
        except (
            OSError,
            TimeoutError,
            ValueError,
            urllib.error.URLError,
            urllib.error.HTTPError,
        ) as exc:
            print(f"[WARN] dashboard ingest failed ({args.dashboard}): {exc}")

    print()
    _print_markdown(report)
    return report


def _csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _print_run_header(config: BenchmarkRunConfig) -> None:
    task_keys = config.tasks or [task.key for task in TASKS]
    methods = config.methods or list(OFFLINE_METHODS if config.offline else ALL_METHODS)
    total = len(task_keys) * len(methods) * len(config.seeds)
    print(f"Running {total} cells: {task_keys} x {methods} x seeds={config.seeds}")
    print("Mode: OFFLINE (no LLM calls)" if config.offline else "Mode: LIVE")


def _post_to_dashboard(base_url: str, report: dict[str, Any]) -> None:
    url = f"{base_url.rstrip('/')}/benchmarks/_ingest"
    body = json.dumps(report).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
        payload = json.loads(resp.read().decode("utf-8"))
    bench_id = payload.get("id")
    if isinstance(bench_id, str) and bench_id:
        print(f"Dashboard benchmark id: {bench_id}")
    else:
        print("Dashboard ingest succeeded.")


def _print_markdown(report: BenchmarkReport) -> None:
    print("| task | method | metric | mean | std | tokens | latency |")
    print("|------|--------|--------|------|-----|--------|---------|")
    metric_by_task = {}
    for cell in report.cells:
        metric_by_task.setdefault(cell.task, cell.metric)
    for row in report.summary:
        metric = metric_by_task.get(row.task, "")
        print(
            f"| {row.task} | {row.method} | {metric} "
            f"| {row.mean:.3f} | {row.std:.3f} "
            f"| {row.tokens_mean} | {row.latency_mean:.1f}s |"
        )

    print("\n## Headline Findings\n")
    for task, finding in report.headline_findings.items():
        print(f"**{task}**: {finding}\n")


def cli() -> None:
    try:
        asyncio.run(main(_parse_args()))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    cli()
