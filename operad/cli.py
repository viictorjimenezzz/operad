"""`operad` command-line entry point.

Subcommands:

    operad run   <config.yaml> --input <input.json>
    operad trace <config.yaml>
    operad graph <config.yaml> [--format json|mermaid]
    operad tail  <trace.jsonl> [--speed 1.0]

Heavy imports (yaml, operad internals) live inside each handler so
`operad --help` starts fast.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="operad")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an agent from a YAML config.")
    run.add_argument("config", type=Path, help="Path to YAML config.")
    run.add_argument(
        "--input", type=Path, required=True, help="Path to input JSON file."
    )

    trace = sub.add_parser("trace", help="Print the agent graph as Mermaid.")
    trace.add_argument("config", type=Path, help="Path to YAML config.")

    graph = sub.add_parser("graph", help="Print the agent graph.")
    graph.add_argument("config", type=Path, help="Path to YAML config.")
    graph.add_argument(
        "--format",
        choices=("json", "mermaid"),
        default="json",
        help="Output format (default: json).",
    )

    tail = sub.add_parser(
        "tail", help="Replay an NDJSON trace log (from JsonlObserver)."
    )
    tail.add_argument("path", type=Path, help="Path to NDJSON trace file.")
    tail.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier (default 1.0). Use 0 for instant.",
    )

    return p


def _load_and_instantiate(path: Path) -> Any:
    from .configs.loader import apply_runtime, instantiate, load

    rc = load(path)
    apply_runtime(rc)
    return instantiate(rc)


def _run(args: argparse.Namespace) -> int:
    import asyncio

    from .configs.loader import ConfigError

    agent = _load_and_instantiate(args.config)

    try:
        raw = args.input.read_text()
    except FileNotFoundError as e:
        raise ConfigError(f"input file not found: {args.input}") from e

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{args.input}: invalid JSON: {e}") from e

    try:
        x = agent.input.model_validate(payload)
    except Exception as e:
        raise ConfigError(f"{args.input}: does not match {agent.input.__name__}: {e}") from e

    agent.build()
    out = asyncio.run(agent.invoke(x))
    print(out.response.model_dump_json())
    return 0


def _trace(args: argparse.Namespace) -> int:
    from .core.graph import to_mermaid

    agent = _load_and_instantiate(args.config)
    agent.build()
    print(to_mermaid(agent._graph))
    return 0


def _graph(args: argparse.Namespace) -> int:
    from .core.graph import to_json, to_mermaid

    agent = _load_and_instantiate(args.config)
    agent.build()
    if args.format == "mermaid":
        print(to_mermaid(agent._graph))
    else:
        print(json.dumps(to_json(agent._graph), indent=2))
    return 0


def _tail(args: argparse.Namespace) -> int:
    import time

    from .configs.loader import ConfigError

    path: Path = args.path
    speed: float = args.speed

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ConfigError(f"trace file not found: {path}") from e

    events: list[dict[str, Any]] = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ConfigError(f"{path}:{lineno}: invalid JSON: {e}") from e

    try:
        from rich.console import Console  # type: ignore[import-not-found]

        console: Any = Console()
        printer = lambda s: console.print(s)  # noqa: E731
    except ImportError:
        printer = print

    for i, ev in enumerate(events):
        kind = ev.get("kind", "?")
        ap = ev.get("agent_path", "?")
        run = str(ev.get("run_id", ""))[:8]
        err = ev.get("error")
        suffix = f" {err['type']}: {err['message']}" if isinstance(err, dict) else ""
        printer(f"[{run}] {kind:5s} {ap}{suffix}")

        if speed > 0 and i + 1 < len(events):
            nxt = events[i + 1]
            dt = float(nxt.get("started_at", 0.0) or 0.0) - float(
                ev.get("started_at", 0.0) or 0.0
            )
            if dt > 0:
                time.sleep(dt / speed)

    return 0


_DISPATCH = {"run": _run, "trace": _trace, "graph": _graph, "tail": _tail}


def main(argv: list[str] | None = None) -> int:
    from .configs.loader import ConfigError

    args = _parser().parse_args(argv)
    handler = _DISPATCH[args.command]
    try:
        return handler(args)
    except ConfigError as e:
        print(f"operad: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
