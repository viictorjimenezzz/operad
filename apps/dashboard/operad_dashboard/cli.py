"""`operad-dashboard` CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import uvicorn

from .app import create_app
from .observer import WebDashboardObserver
from .replay import replay_file


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="operad-dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=7860)
    p.add_argument(
        "--replay",
        default=None,
        help="JSONL trace file to replay instead of waiting for live events",
    )
    p.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier; 0 = as fast as possible",
    )
    p.add_argument(
        "--langfuse-url",
        default=os.environ.get("LANGFUSE_PUBLIC_URL"),
        help=(
            "Public base URL of a Langfuse instance reachable from the "
            "user's browser (e.g. http://localhost:3000). When set, "
            "run-detail pages render a 'View in Langfuse' link to "
            "{base}/trace/{run_id}. Defaults to the LANGFUSE_PUBLIC_URL "
            "environment variable."
        ),
    )
    p.add_argument(
        "--benchmark-dir",
        default=os.environ.get("OPERAD_DASHBOARD_BENCHMARK_DIR", "./.benchmarks/"),
        help=(
            "Directory scanned once on startup for benchmark report JSON files. "
            "Defaults to OPERAD_DASHBOARD_BENCHMARK_DIR or ./.benchmarks/."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.replay:
        return _run_replay(args)
    return _run_live(args)


def _run_live(args: argparse.Namespace) -> int:
    app = create_app(
        langfuse_url=args.langfuse_url,
        benchmark_dir=args.benchmark_dir,
    )
    print(
        f"Dashboard live at http://{args.host}:{args.port}\n"
        "Run your operad agent in the same Python process, "
        "or attach via `operad.dashboard.attach"
        f"(port={args.port})` from another process.",
        file=sys.stderr,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def _run_replay(args: argparse.Namespace) -> int:
    observer = WebDashboardObserver()
    app = create_app(
        observer=observer,
        auto_register=False,
        langfuse_url=args.langfuse_url,
        benchmark_dir=args.benchmark_dir,
    )

    async def _replay_then_idle() -> None:
        count = await replay_file(args.replay, observer, speed=args.speed)
        print(f"Replayed {count} events from {args.replay}", file=sys.stderr)

    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(config)

    async def _serve() -> None:
        replay_task = asyncio.create_task(_replay_then_idle())
        try:
            await server.serve()
        finally:
            replay_task.cancel()

    asyncio.run(_serve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
